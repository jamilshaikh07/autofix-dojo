{{/*
Expand the name of the chart.
*/}}
{{- define "autofix-dojo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "autofix-dojo.fullname" -}}
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
{{- define "autofix-dojo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "autofix-dojo.labels" -}}
helm.sh/chart: {{ include "autofix-dojo.chart" . }}
{{ include "autofix-dojo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: autofix-dojo
{{- end }}

{{/*
Selector labels
*/}}
{{- define "autofix-dojo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "autofix-dojo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "autofix-dojo.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "autofix-dojo.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
DefectDojo secret name
*/}}
{{- define "autofix-dojo.defectdojoSecretName" -}}
{{- if .Values.defectdojo.existingSecret }}
{{- .Values.defectdojo.existingSecret }}
{{- else }}
{{- include "autofix-dojo.fullname" . }}-defectdojo
{{- end }}
{{- end }}
