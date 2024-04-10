# Create a new namespace for cert manager to run in
resource "kubernetes_namespace" "cert_manager_namespace" {
  metadata {
    labels = {
      name = "cert-manager"
    }
    name = "cert-manager"
  }
}

# Add the helm chart and pin to a version
resource "helm_release" "cert-manager" {
  name = "cert-manager-upgrade"

  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = "1.14.3"
  namespace  = kubernetes_namespace.cert_manager_namespace.metadata[0].name


  set {
    name  = "installCRDs"
    value = "true"
  }
}