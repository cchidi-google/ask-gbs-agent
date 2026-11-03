terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  required_apis = toset([
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "discoveryengine.googleapis.com",
    "dlp.googleapis.com",
  ])
}

resource "google_project_service" "enabled_apis" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "ask_gbs_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = "ask-gbs-repo"
  description   = "Container repository for Ask GBS Enterprise Helpdesk ADK Agent"
  format        = "DOCKER"

  depends_on = [google_project_service.enabled_apis]
}

resource "google_storage_bucket" "staging_bucket" {
  name                        = "${var.project_id}-ask-gbs-staging"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "servicenow_webhook_secret" {
  project   = var.project_id
  secret_id = "ask-gbs-servicenow-webhook"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret" "coupa_readonly_token" {
  project   = var.project_id
  secret_id = "ask-gbs-coupa-readonly-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_service_account" "ask_gbs_agent_sa" {
  project      = var.project_id
  account_id   = "ask-gbs-agent-sa"
  display_name = "Ask GBS ADK Agent Least-Privilege Runtime SA"
  description  = "Least-privilege identity for Cloud Run, Vertex AI, Secret Manager, DLP, and Cloud Trace"
}

locals {
  agent_sa_roles = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/dlp.user",
    "roles/discoveryengine.viewer",
  ])
}

resource "google_project_iam_member" "agent_sa_bindings" {
  for_each = local.agent_sa_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.ask_gbs_agent_sa.email}"
}

resource "google_cloud_run_v2_service" "ask_gbs_service" {
  name     = var.service_name
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.ask_gbs_agent_sa.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GEMINI_FLASH_MODEL"
        value = "gemini-2.5-flash"
      }
      env {
        name  = "GEMINI_PRO_MODEL"
        value = "gemini-2.5-pro"
      }
      env {
        name  = "ENABLE_SECRET_MANAGER"
        value = "true"
      }
      env {
        name  = "ENABLE_CLOUD_LOGGING"
        value = "true"
      }
      env {
        name  = "ENABLE_CLOUD_TRACE"
        value = "true"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 3
        period_seconds        = 5
        failure_threshold     = 6
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.agent_sa_bindings,
  ]
}
