variable "project_id" {
  description = "Google Cloud Project ID hosting Ask GBS ADK Agent and Gemini Enterprise"
  type        = string
  default     = "aecom-demo-uc1"
}

variable "region" {
  description = "Primary GCP region for Cloud Run, Artifact Registry, and Vertex AI"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run v2 service name for Ask GBS ADK Agent"
  type        = string
  default     = "ask-gbs-agent"
}

variable "container_image" {
  description = "Container image URI in Artifact Registry for Cloud Run deployment"
  type        = string
  default     = "us-central1-docker.pkg.dev/aecom-demo-uc1/ask-gbs-repo/ask-gbs-agent:latest"
}

variable "min_instance_count" {
  description = "Minimum warm Cloud Run instances to eliminate live demo cold starts"
  type        = number
  default     = 1
}

variable "max_instance_count" {
  description = "Maximum autoscaled Cloud Run instances"
  type        = number
  default     = 10
}
