from flask import Flask, request
import time
import logging
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# ------------------------------------------------------------------------------
# ✅ 1. Configure tracing with Jaeger collector inside Docker
# ------------------------------------------------------------------------------

trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": "observability-poc-app"}))
)

# ✅ Important: use the service name "jaeger" (not localhost) since both run in the same Docker network
jaeger_exporter = JaegerExporter(
    collector_endpoint="http://jaeger:14268/api/traces",
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# ------------------------------------------------------------------------------
# Flask + Prometheus setup
# ------------------------------------------------------------------------------

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

REQUESTS = Counter(
    'http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'http_status']
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('poc_app')


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/')
def index():
    with tracer.start_as_current_span('handle-index'):
        start = time.time()
        logger.info('handling / request', extra={'path': '/'})
        time.sleep(0.05)
        REQUESTS.labels(method='GET', endpoint='/', http_status='200').inc()
        return 'Hello — Observability POC!'


@app.route('/sleep')
def slow():
    with tracer.start_as_current_span('handle-sleep'):
        t = float(request.args.get('t', '0.2'))
        logger.info('handling /sleep request', extra={'t': t})
        time.sleep(t)
        REQUESTS.labels(method='GET', endpoint='/sleep', http_status='200').inc()
        return f'slept {t}s'


# ------------------------------------------------------------------------------
# ✅ 2. Run on correct interface and port for Docker
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)