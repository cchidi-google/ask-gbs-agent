output "cloud_run_service_url" {
  description = "HTTPS endpoint URL of the deployed Ask GBS Cloud Run service"
  value       = google_cloud_run_v2_service.ask_gbs_service.uri
}

output "agent_service_account_email" {
  description = "Least-privilege Service Account email for Ask GBS runtime and Gemini Enterprise registration"
  value       = google_service_account.ask_gbs_agent_sa.email
}

output "staging_bucket_uri" {
  description = "GCS staging bucket URI for Vertex AI Agent Engine artifacts"
  value       = "gs://${google_storage_bucket.staging_bucket.name}"
}

output "artifact_registry_repository" {
  description = "Artifact Registry Docker repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ask_gbs_repo.repository_id}"
}
