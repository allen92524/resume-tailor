"""Tests for the Helm chart using `helm template` to render and validate YAML."""

import subprocess
import yaml

CHART_PATH = "helm/resume-tailor"


def _helm_template(set_values: dict | None = None) -> list[dict]:
    """Run `helm template` and return all rendered YAML documents."""
    cmd = ["helm", "template", "test-release", CHART_PATH]
    for key, val in (set_values or {}).items():
        cmd.extend(["--set", f"{key}={val}"])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    docs = list(yaml.safe_load_all(result.stdout))
    return [d for d in docs if d is not None]


def _find_by_kind(docs: list[dict], kind: str) -> dict | None:
    """Find the first document of a given Kind."""
    for doc in docs:
        if doc.get("kind") == kind:
            return doc
    return None


def _find_all_by_kind(docs: list[dict], kind: str) -> list[dict]:
    """Find all documents of a given Kind."""
    return [doc for doc in docs if doc.get("kind") == kind]


# ── Basic rendering ─────────────────────────────────────────────────


class TestHelmTemplateRenders:
    """Verify that helm template produces valid YAML without errors."""

    def test_renders_without_error(self):
        docs = _helm_template()
        assert len(docs) > 0

    def test_produces_expected_resource_types(self):
        docs = _helm_template()
        kinds = {doc.get("kind") for doc in docs}
        assert "Deployment" in kinds
        assert "Service" in kinds
        assert "Secret" in kinds

    def test_all_docs_have_metadata(self):
        docs = _helm_template()
        for doc in docs:
            assert "metadata" in doc, f"{doc.get('kind')} missing metadata"
            assert "name" in doc["metadata"], f"{doc.get('kind')} missing metadata.name"


# ── Deployment ──────────────────────────────────────────────────────


class TestDeployment:
    """Verify the rendered Deployment resource."""

    def test_deployment_exists(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        assert dep is not None

    def test_default_replica_count(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        assert dep["spec"]["replicas"] == 1

    def test_custom_replica_count(self):
        docs = _helm_template({"replicaCount": "3"})
        dep = _find_by_kind(docs, "Deployment")
        assert dep["spec"]["replicas"] == 3

    def test_image_uses_default_values(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "resume-tailor:latest"

    def test_custom_image_tag(self):
        docs = _helm_template({"image.tag": "v1.3.0"})
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "resume-tailor:v1.3.0"

    def test_container_port_8000(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        ports = container["ports"]
        assert any(p["containerPort"] == 8000 for p in ports)

    def test_liveness_probe_health_endpoint(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        probe = container["livenessProbe"]
        assert probe["httpGet"]["path"] == "/api/v1/health"
        assert probe["httpGet"]["port"] == "http"

    def test_readiness_probe_health_endpoint(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        probe = container["readinessProbe"]
        assert probe["httpGet"]["path"] == "/api/v1/health"
        assert probe["httpGet"]["port"] == "http"

    def test_resource_limits_set(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        resources = container["resources"]
        assert "limits" in resources
        assert "cpu" in resources["limits"]
        assert "memory" in resources["limits"]

    def test_env_from_secret_and_configmap(self):
        docs = _helm_template()
        dep = _find_by_kind(docs, "Deployment")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env_from = container["envFrom"]
        ref_names = []
        for ef in env_from:
            if "secretRef" in ef:
                ref_names.append(("secret", ef["secretRef"]["name"]))
            if "configMapRef" in ef:
                ref_names.append(("configmap", ef["configMapRef"]["name"]))
        secret_names = [n for t, n in ref_names if t == "secret"]
        cm_names = [n for t, n in ref_names if t == "configmap"]
        assert len(secret_names) >= 1, "Deployment should reference a secret"
        assert len(cm_names) >= 1, "Deployment should reference a configmap"


# ── Service ─────────────────────────────────────────────────────────


class TestService:
    """Verify the rendered Service resource."""

    def test_service_exists(self):
        docs = _helm_template()
        svc = _find_by_kind(docs, "Service")
        assert svc is not None

    def test_service_port_8000(self):
        docs = _helm_template()
        svc = _find_by_kind(docs, "Service")
        ports = svc["spec"]["ports"]
        assert any(p["port"] == 8000 for p in ports)

    def test_service_type_clusterip(self):
        docs = _helm_template()
        svc = _find_by_kind(docs, "Service")
        assert svc["spec"]["type"] == "ClusterIP"

    def test_service_has_selector(self):
        docs = _helm_template()
        svc = _find_by_kind(docs, "Service")
        assert svc["spec"]["selector"] is not None
        assert len(svc["spec"]["selector"]) > 0


# ── Secret ──────────────────────────────────────────────────────────


class TestSecret:
    """Verify the rendered Secret resource."""

    def test_secret_exists(self):
        docs = _helm_template()
        secret = _find_by_kind(docs, "Secret")
        assert secret is not None

    def test_secret_type_opaque(self):
        docs = _helm_template()
        secret = _find_by_kind(docs, "Secret")
        assert secret["type"] == "Opaque"

    def test_secret_contains_api_key_field(self):
        docs = _helm_template()
        secret = _find_by_kind(docs, "Secret")
        assert "ANTHROPIC_API_KEY" in secret["data"]

    def test_secret_api_key_base64_encoded(self):
        import base64

        docs = _helm_template({"apiKey": "sk-test-key-123"})
        secret = _find_by_kind(docs, "Secret")
        encoded = secret["data"]["ANTHROPIC_API_KEY"]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "sk-test-key-123"


# ── Ingress ─────────────────────────────────────────────────────────


class TestIngress:
    """Verify Ingress is conditionally rendered."""

    def test_ingress_disabled_by_default(self):
        docs = _helm_template()
        ingress = _find_by_kind(docs, "Ingress")
        assert ingress is None

    def test_ingress_enabled(self):
        docs = _helm_template({"ingress.enabled": "true"})
        ingress = _find_by_kind(docs, "Ingress")
        assert ingress is not None


# ── ServiceMonitor ──────────────────────────────────────────────────


class TestServiceMonitor:
    """Verify ServiceMonitor is conditionally rendered."""

    def test_servicemonitor_disabled_by_default(self):
        docs = _helm_template()
        sm = _find_by_kind(docs, "ServiceMonitor")
        assert sm is None

    def test_servicemonitor_enabled(self):
        docs = _helm_template({"metrics.serviceMonitor.enabled": "true"})
        sm = _find_by_kind(docs, "ServiceMonitor")
        assert sm is not None


# ── ConfigMap ───────────────────────────────────────────────────────


class TestConfigMap:
    """Verify the ConfigMap resource."""

    def test_configmap_exists(self):
        docs = _helm_template()
        cms = _find_all_by_kind(docs, "ConfigMap")
        assert len(cms) >= 1

    def test_grafana_dashboard_disabled_by_default(self):
        docs = _helm_template()
        cms = _find_all_by_kind(docs, "ConfigMap")
        dashboard_cms = [
            cm for cm in cms if "dashboard" in cm["metadata"]["name"]
        ]
        assert len(dashboard_cms) == 0

    def test_grafana_dashboard_enabled(self):
        docs = _helm_template({"metrics.grafanaDashboard.enabled": "true"})
        cms = _find_all_by_kind(docs, "ConfigMap")
        dashboard_cms = [
            cm for cm in cms if "dashboard" in cm["metadata"]["name"]
        ]
        assert len(dashboard_cms) >= 1
