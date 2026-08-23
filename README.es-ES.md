

# LogForge

Todo sistema de producción genera registros. Sin una canalización estructurada, la depuración implica conectarse por SSH a un servidor y ejecutar `grep`, lo cual no funciona cuando los registros están dispersos en múltiples instancias de servicio, cuando necesitas responder "¿cuántos eventos ERROR emitió payment-service en los últimos 10 minutos?", o cuando deseas recibir una alerta antes de que un problema se convierta en una interrupción.

La mayoría de los colectores de registros escriben directamente en una base de datos en la ruta de ingestión. Bajo carga en picos, esto crea contrapresión en el punto final de ingestión y puede bloquear los hilos de las solicitudes. LogForge separa la ruta de escritura (Kafka, enviar y olvidar) de la ruta de almacenamiento (inserción por lotes por un consumidor separado), brindando al punto final HTTP de ingestión un tiempo de respuesta constante de menos de un milisegundo, independientemente de la carga de la base de datos.

---

## Arquitectura

```
Cliente HTTP POST /logs
    |
    v
Servicio de Ingestión (:8001)         -- FastAPI, valida la carga útil, verifica el límite de tasa de Redis
    |   acks=all, reintentos=5, compresión lz4
    |
    v
Kafka (logs-topic)                   -- capa de durabilidad; los mensajes sobreviven a los reinicios del procesador
    |
    v
Servicio Procesador                    -- Consumidor confluent-kafka
    |   lote de 100 registros O tiempo de espera de 500 ms, lo que ocurra primero
    |   ON CONFLICT DO NOTHING para reenvío idempotente
    |   registros fallidos -> logs-topic-dlq
    v
PostgreSQL (tabla logs)
    |   Índice GIN en to_tsvector(mensaje) para búsqueda de texto completo
    |   Índice de timestamp para consultas de rango
    v
Servicio de Consulta (:8002)          -- FastAPI, solo lectura
    |   filtrado por servicio/nivel/rango de tiempo + búsqueda de texto completo
    |   paginación basada en cursor, caché Redis (TTL 60 s, clave MD5)
    |   agregaciones de tasa de errores (date_trunc por minuto/hora/día)
    v
Servicio de Alertas                    -- ciclo en segundo plano, consulta periódica cada 60 s
        lee alert_rules desde PostgreSQL
        cuenta los eventos coincidentes en cada ventana de regla
        deduplica: omite si existe un alert_event no reconocido en la misma ventana
        escribe alert_events; registra WARNING
```

Cuatro procesos separados se asignan a cuatro contenedores independientes en Docker Compose. La cola DLQ (`logs-topic-dlq`) actúa como cuarentena para los registros que fallan en la validación o en la inserción por lotes tras 3 reintentos: inspeccionable sin pérdida de datos.

---

## Decisiones Clave de Diseño

**Kafka como capa de durabilidad, no como escritura sincrónica en base de datos.** El servicio de ingestión escribe en Kafka (`acks=all`) y devuelve HTTP 202 de inmediato. Si PostgreSQL cae, Kafka retiene los mensajes durante 168 horas (configurable). Una escritura sincrónica en Postgres en la ruta de ingestión haría que la latencia y disponibilidad del punto final HTTP dependieran directamente de la base de datos. Compensación: los mensajes son "aceptados" antes de ser consultables; existe un retraso inherente entre la ingestión y la visibilidad en la API de consulta igual al intervalo de vaciado por lotes (100 registros o 500 ms).

**Inserción por lotes con `ON CONFLICT DO NOTHING`, no inserciones por registro.** El procesador acumula hasta 100 registros antes de llamar a `executemany`. Un solo viaje de ida y vuelta para 100 filas es aproximadamente 50 veces más rápido que 100 inserciones individuales. `ON CONFLICT DO NOTHING` hace que el reenvío sea seguro cuando el procesador se reinicia después de un commit pero antes del commit del offset de Kafka. Compensación: un lote fallido envía los 100 registros a la DLQ, lo que puede incluir algunos registros que en realidad eran válidos.

**Ventana deslizante de conjunto ordenado de Redis para límite de tasa, no un balde de tokens en memoria.** `RedisRateLimiter` usa `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD` en un pipeline para contar solicitudes en los últimos N segundos por IP. Esto sobrevive a los reinicios del servicio de ingestión y funcionaría correctamente con múltiples réplicas del servicio. Un contador puramente en memoria se reiniciaría y daría un límite independiente a cada réplica. Compensación: cada solicitud de ingestión paga un viaje de ida y vuelta a Redis.

**Alertas como ciclo de consulta periódica, no como disparador en streaming.** El servicio de alertas ejecuta un `SELECT COUNT(*)` contra la tabla `logs` cada 60 segundos. Un enfoque en streaming (Kafka Streams o mecanismo basado en triggers) permitiría detectar latencia en segundos, pero requiere un clúster Kafka Streams o una integración LISTEN/NOTIFY de PostgreSQL. El enfoque por consulta periódica es simple, correcto y la resolución de 60 segundos es aceptable para la mayoría de los requisitos de latencia de alertas. Compensación: las alertas pueden dispararse hasta 60 segundos después de cruzarse un umbral.

**Caché de consultas con entradas de Redis claveadas por MD5, no caché a nivel HTTP.** Los parámetros de consulta (servicio, nivel, rango de tiempo, página) se serializan y hash-ean con MD5 para formar la clave de caché. Esto brinda granularidad por consulta: una consulta para `service=payments&level=ERROR` se cachea independientemente de `service=auth&level=ERROR`. El caché a nivel HTTP (ETags, Cache-Control) requeriría que los clientes implementaran GET condicional. Compensación: resultados obsoletos por hasta 60 segundos después de que lleguen nuevos registros que coincidan con la consulta.

---

## Stack Tecnológico

| Componente | Justificación |
|---|---|
| **Kafka (Confluent Platform)** | Cola de mensajes duradera; desacopla la latencia de ingestión de la latencia de almacenamiento; retención de registros de 168 horas |
| **confluent-kafka** | Cliente Python oficial de Confluent; de nivel inferior que kafka-python pero más estable para uso en producción |
| **FastAPI** | Puntos finales asincrónicos para servicios de ingestión y consulta; validación automática mediante modelos Pydantic |
| **asyncpg** | Controlador asíncrono de PostgreSQL para el servicio de consulta; agrupación de conexiones con tamaño mínimo/máximo configurable |
| **PostgreSQL 16** | Almacenamiento principal; índice GIN en `to_tsvector(message)` permite búsqueda de texto completo; `date_trunc` para agregaciones |
| **Redis 7** | Limitador de tasa (conjuntos ordenados, servicio de ingestión) y caché de consultas (servicio de consulta, índice de DB separado) |
| **Pydantic v2** | Modelos compartidos `LogEntry` y `KafkaMessage` validados en el límite de ingestión; `model_validate_json` en el procesador |
| **pydantic-settings** | Clases `BaseSettings` por servicio con aislamiento de prefijo de env (`KAFKA_`, `DATABASE_`, `REDIS_`) |
| **testcontainers** | Las pruebas de integración inician contenedores reales de Kafka, Postgres y Redis; sin simulación (mocking) de infraestructura |

---

## Ejecución Local

```bash
git clone https://github.com/Aliipou/logforge.git
cd logforge

# Instalar dependencias (todos los servicios comparten un pyproject.toml)
pip install -e ".[dev]"

# Iniciar toda la infraestructura y servicios
docker compose up

# Servicios:
#   API de Ingestión:  http://localhost:8001
#   API de Consulta:   http://localhost:8002
#   Kafka:             localhost:9092
#   PostgreSQL:        localhost:5432
#   Redis:             localhost:6379

# Ingresar un registro
curl -X POST http://localhost:8001/logs \
  -H "Content-Type: application/json" \
  -d '{"service_name": "payments", "level": "ERROR", "message": "charge failed", "metadata": {"user_id": 42}}'

# Consultar registros
curl "http://localhost:8002/logs?service=payments&level=ERROR&page_size=10"

# Búsqueda de texto completo
curl "http://localhost:8002/logs?q=charge+failed"

# Agregación de tasa de errores por minuto
curl "http://localhost:8002/logs/aggregations?service=payments&level=ERROR&interval=minute"
```

Ejecutar pruebas:

```bash
# Pruebas unitarias (sin servicios externos)
pytest tests/unit/ -v

# Pruebas de integración (requiere Docker — testcontainers inicia Kafka/Postgres/Redis)
pytest tests/integration/ -v
```

---

## Despliegue

- **Zookeeper + Kafka** — obligatorio; `docker-compose.yml` utiliza `confluentinc/cp-kafka:7.6.0` con verificaciones de salud que aseguran que Kafka esté listo antes de que inicie el procesador
- **PostgreSQL 16** — el archivo `common/sql/init.sql` crea las tablas `logs`, `alert_rules` y `alert_events` con índices; se monta como un script de inicialización de Docker
- **Redis 7** — se utilizan dos bases de datos lógicas: índice 0 para el limitador de tasa de ingestión, índice 1 para el caché de consultas
- **Cuatro contenedores** — ingestión, procesador, consulta y alertas se ejecutan como servicios separados en `docker-compose.yml`; cada uno tiene `restart: unless-stopped`
- **Monitoreo de DLQ** — `logs-topic-dlq` debe monitorearse; un alto volumen en DLQ indica incompatibilidades de esquema o fallos sistemáticos de escritura en Postgres

Las variables de entorno siguen prefijos por servicio:

```
KAFKA_BOOTSTRAP_SERVERS    # para ingestión y procesador
KAFKA_TOPIC                # predeterminado: logs-topic
DATABASE_URL               # para procesador, consulta y alertas
REDIS_URL                  # para ingestión (limitador de tasa) y consulta (caché)
RATE_LIMIT_PER_MINUTE      # predeterminado: 100
```

---

## Limitaciones Conocidas / TODO

- **Sin autenticación en los puntos finales de ingestión o consulta.** Cualquier cliente con acceso de red puede enviar logs por POST o leer todos los registros. Agregar una clave API o middleware JWT antes de exponer públicamente cualquiera de los servicios.
- **Partición única de Kafka / broker único.** `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1` y un solo broker significa sin tolerancia a fallos. Un entorno de producción necesita como mínimo 3 brokers y un factor de replicación de 2.
- **Entrega de alertas solo mediante registros.** El servicio de alertas escribe líneas de registro `WARNING` y filas `alert_events`; no envía mensajes de Slack, correos electrónicos ni llamadas webhook. La integración de entrega está pendiente.
- **Sin registro de esquemas.** El formato de mensaje de Kafka (modelo Pydantic `KafkaMessage`) se comparte mediante una importación de Python. Si el esquema cambia, el productor y el consumidor deben desplegarse juntos. Un registro de esquemas (Confluent Schema Registry o Apicurio) impondría compatibilidad a nivel de Kafka.
- **Granularidad de DLQ en inserción por lotes.** Un lote fallido envía todos los registros del lote a la DLQ, incluyendo aquellos que podrían haber sido válidos individualmente. El reintento por registro antes de la DLQ requeriría reestructurar el ciclo del procesador.
- **Sin política de retención.** La tabla `logs` crece sin límite. Agregar un calendario de partición `pg_partman` o un trabajo periódico `DELETE WHERE timestamp < NOW() - INTERVAL`.
