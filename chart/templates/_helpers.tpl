{{/*
Expand the name of the chart.
*/}}
{{- define "chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "chart.labels" -}}
helm.sh/chart: {{ include "chart.chart" . }}
{{ include "chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database ConfigMap Name
*/}}
{{- define "chart.mobotDatabaseConfigMapName" -}}
  {{- if .Values.mobotDatabase.configMap.external }}
    {{- .Values.mobotDatabase.configMap.name }}
  {{- else }}
    {{- include "chart.fullname" . }}-{{ .Values.mobotDatabase.configMap.name }}
  {{- end }}
{{- end }}

{{/*
Database Secret Name
*/}}
{{- define "chart.mobotDatabaseSecretName" -}}
  {{- if .Values.mobotDatabase.secret.external }}
    {{- .Values.mobotDatabase.secret.name }}
  {{- else }}
    {{- include "chart.fullname" . }}-{{ .Values.mobotDatabase.secret.name }}
  {{- end }}
{{- end }}

{{/*
Mobot ConfigMap Name
*/}}
{{- define "chart.mobotConfigMapName" -}}
  {{- if .Values.mobotConfig.configMap.external }}
    {{- .Values.mobotConfig.configMap.name }}
  {{- else }}
    {{- include "chart.fullname" . }}-{{ .Values.mobotConfig.configMap.name }}
  {{- end }}
{{- end }}

{{/*
Mobot Secret Name
*/}}
{{- define "chart.mobotSecretName" -}}
  {{- if .Values.mobotConfig.secret.external }}
    {{- .Values.mobotConfig.secret.name }}
  {{- else }}
    {{- include "chart.fullname" . }}-{{ .Values.mobotConfig.secret.name }}
  {{- end }}
{{- end }}

{{/*
Mobot Store Numbers
*/}}
{{- define "chart.mobotStoreNumbers" -}}
  {{- if .Values.mobotConfig.configMap.external }}
    {{- toYaml (lookup "v1" "ConfigMap" .Release.Namespace .Values.mobotDatabase.configMap.name ).data.STORE_NUMBERS }}
  {{- else }}
{"numbers": {{ .Values.mobotConfig.storeNumbers | toJson }}}
  {{- end }}
{{- end }}

{{/*
Mobot Hostname
*/}}
{{- define "chart.mobotHostname" -}}
  {{- if .Values.mobotConfig.configMap.external }}
    {{- (lookup "v1" "ConfigMap" .Release.Namespace .Values.mobotDatabase.configMap.name ).data.HOSTNAME }}
  {{- else }}
    {{- .Values.mobotConfig.hostname }}
  {{- end }}
{{- end }}
