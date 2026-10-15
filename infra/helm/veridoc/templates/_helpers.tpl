{{/*
Chart name (optionally overridden).
*/}}
{{- define "veridoc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified release name.
*/}}
{{- define "veridoc.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "veridoc.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels (no component — add app.kubernetes.io/component per resource).
*/}}
{{- define "veridoc.labels" -}}
helm.sh/chart: {{ include "veridoc.chart" . }}
{{ include "veridoc.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: veridoc
{{- end -}}

{{/*
Selector labels (stable across upgrades — never include version/component here;
component is added explicitly where a per-workload selector is required).
*/}}
{{- define "veridoc.selectorLabels" -}}
app.kubernetes.io/name: {{ include "veridoc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "veridoc.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "veridoc.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Component Service names.
*/}}
{{- define "veridoc.api.fullname" -}}{{ printf "%s-api" (include "veridoc.fullname" .) | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "veridoc.ai.fullname" -}}{{ printf "%s-ai" (include "veridoc.fullname" .) | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "veridoc.web.fullname" -}}{{ printf "%s-web" (include "veridoc.fullname" .) | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "veridoc.postgresql.fullname" -}}{{ printf "%s-postgresql" (include "veridoc.fullname" .) | trunc 63 | trimSuffix "-" }}{{- end -}}

{{/*
Image reference: ghcr.io/<owner>/<image>:<tag>. `tag` defaults to AppVersion.
Call as: {{ include "veridoc.image" (dict "root" . "image" .Values.api.image) }}
*/}}
{{- define "veridoc.image" -}}
{{- $tag := .root.Values.image.tag | default .root.Chart.AppVersion -}}
{{- printf "%s/%s/%s:%s" .root.Values.image.registry .root.Values.image.owner .image $tag -}}
{{- end -}}

{{/*
Bundled Postgres image reference (digest-pinned when provided).
*/}}
{{- define "veridoc.postgresql.image" -}}
{{- $p := .Values.postgresql.image -}}
{{- if $p.digest -}}
{{- printf "%s:%s@%s" $p.repository $p.tag $p.digest -}}
{{- else -}}
{{- printf "%s:%s" $p.repository $p.tag -}}
{{- end -}}
{{- end -}}

{{/*
Name of the Secret holding the AI service's AI_DATABASE_URL, and its key.
Bundled DB or an inline externalDatabase.url => the chart-managed "<fullname>-db"
Secret; otherwise a user-managed externalDatabase.existingSecret.
*/}}
{{- define "veridoc.db.secretName" -}}
{{- if or .Values.postgresql.enabled .Values.externalDatabase.url -}}
{{- printf "%s-db" (include "veridoc.fullname" .) -}}
{{- else -}}
{{- required "postgresql.enabled=false requires externalDatabase.url or externalDatabase.existingSecret" .Values.externalDatabase.existingSecret -}}
{{- end -}}
{{- end -}}

{{- define "veridoc.db.secretKey" -}}
{{- if or .Values.postgresql.enabled .Values.externalDatabase.url -}}
database-url
{{- else -}}
{{- default "url" .Values.externalDatabase.existingSecretKey -}}
{{- end -}}
{{- end -}}

{{/*
Resolve (and persist) the bundled Postgres password. Priority:
  postgresql.auth.password -> existing chart Secret (preserve) -> random.
*/}}
{{- define "veridoc.db.password" -}}
{{- $pw := .Values.postgresql.auth.password -}}
{{- if not $pw -}}
{{- $existing := (lookup "v1" "Secret" .Release.Namespace (printf "%s-db" (include "veridoc.fullname" .))) -}}
{{- if and $existing (index $existing.data "postgres-password") -}}
{{- $pw = (index $existing.data "postgres-password" | b64dec) -}}
{{- else -}}
{{- $pw = randAlphaNum 24 -}}
{{- end -}}
{{- end -}}
{{- $pw -}}
{{- end -}}

{{/*
Whether an inference API key is configured (inline or via existing Secret).
*/}}
{{- define "veridoc.inference.enabled" -}}
{{- if or .Values.secrets.inferenceApiKey .Values.secrets.existingSecret -}}true{{- end -}}
{{- end -}}

{{- define "veridoc.inference.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-inference" (include "veridoc.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "veridoc.inference.secretKey" -}}
{{- if .Values.secrets.existingSecret -}}
{{- default "inference-api-key" .Values.secrets.existingSecretKey -}}
{{- else -}}
inference-api-key
{{- end -}}
{{- end -}}
