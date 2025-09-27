{{/*
Expand the name of the chart.
*/}}
{{- define "wind-power.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "wind-power.fullname" -}}
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
{{- define "wind-power.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "wind-power.labels" -}}
helm.sh/chart: {{ include "wind-power.chart" . }}
{{ include "wind-power.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "wind-power.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wind-power.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "wind-power.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}
{{- default (include "wind-power.fullname" .) .Values.global.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.global.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL fullname
*/}}
{{- define "wind-power.postgresql.fullname" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "wind-power.fullname" .) }}
{{- else }}
{{- .Values.externalPostgresql.host }}
{{- end }}
{{- end }}

{{/*
PostgreSQL secret name
*/}}
{{- define "wind-power.postgresql.secretName" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "wind-power.fullname" .) }}
{{- else }}
{{- printf "%s-external-postgresql" (include "wind-power.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Redis fullname
*/}}
{{- define "wind-power.redis.fullname" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis" (include "wind-power.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
RabbitMQ fullname
*/}}
{{- define "wind-power.rabbitmq.fullname" -}}
{{- if .Values.rabbitmq.enabled }}
{{- printf "%s-rabbitmq" (include "wind-power.fullname" .) }}
{{- else }}
{{- .Values.externalRabbitmq.host }}
{{- end }}
{{- end }}

{{/*
Check if any microservice is enabled
*/}}
{{- define "wind-power.microservicesEnabled" -}}
{{- if or .Values.microservices.meteorological.enabled .Values.microservices.scada.enabled .Values.microservices.powerPrediction.enabled .Values.microservices.report.enabled .Values.microservices.tenant.enabled .Values.microservices.windFarm.enabled }}
true
{{- else }}
false
{{- end }}
{{- end }}

{{/*
Create environment variables for microservices
*/}}
{{- define "wind-power.microservice.env" -}}
- name: NODE_ENV
  value: {{ .Values.global.environment | quote }}
- name: DB_HOST
  value: {{ include "wind-power.postgresql.fullname" . | quote }}
- name: DB_PORT
  value: "5432"
- name: DB_USER
  value: {{ .Values.postgresql.auth.username | quote }}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "wind-power.postgresql.secretName" . }}
      key: postgres-password
- name: REDIS_HOST
  value: {{ include "wind-power.redis.fullname" . | quote }}
- name: REDIS_PORT
  value: "6379"
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "wind-power.fullname" . }}-secrets
      key: redis-password
- name: RABBITMQ_HOST
  value: {{ include "wind-power.rabbitmq.fullname" . | quote }}
- name: RABBITMQ_PORT
  value: "5672"
- name: RABBITMQ_USER
  value: {{ .Values.rabbitmq.auth.username | quote }}
- name: RABBITMQ_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "wind-power.fullname" . }}-secrets
      key: rabbitmq-password
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "wind-power.fullname" . }}-secrets
      key: jwt-secret
- name: LOG_LEVEL
  value: {{ .Values.global.logLevel | default "info" | quote }}
- name: METRICS_ENABLED
  value: {{ .Values.global.metricsEnabled | default "true" | quote }}
{{- end }}

{{/*
Create health check probes
*/}}
{{- define "wind-power.healthProbes" -}}
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
startupProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 30
{{- end }}

{{/*
Create security context
*/}}
{{- define "wind-power.securityContext" -}}
securityContext:
  allowPrivilegeEscalation: false
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  capabilities:
    drop:
    - ALL
{{- end }}

{{/*
Create pod disruption budget
*/}}
{{- define "wind-power.pdb" -}}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "wind-power.fullname" . }}-{{ .component }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "wind-power.labels" . | nindent 4 }}
    app.kubernetes.io/component: {{ .component }}
spec:
  {{- if .Values.podDisruptionBudget.minAvailable }}
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  {{- end }}
  {{- if .Values.podDisruptionBudget.maxUnavailable }}
  maxUnavailable: {{ .Values.podDisruptionBudget.maxUnavailable }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "wind-power.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create network policy
*/}}
{{- define "wind-power.networkPolicy" -}}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "wind-power.fullname" . }}-{{ .component }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "wind-power.labels" . | nindent 4 }}
    app.kubernetes.io/component: {{ .component }}
spec:
  podSelector:
    matchLabels:
      {{- include "wind-power.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: {{ .component }}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: {{ .Release.Namespace }}
    - podSelector:
        matchLabels:
          app.kubernetes.io/part-of: wind-power
    ports:
    - protocol: TCP
      port: {{ .port }}
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: {{ .Release.Namespace }}
    ports:
    - protocol: TCP
      port: 5432
    - protocol: TCP
      port: 6379
    - protocol: TCP
      port: 5672
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
{{- end }}