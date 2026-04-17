{{- define "estategap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "estategap.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "estategap.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "estategap.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "estategap.labels" -}}
helm.sh/chart: {{ include "estategap.chart" . }}
app.kubernetes.io/name: {{ include "estategap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: estategap
{{- end -}}

{{- define "estategap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "estategap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: estategap
{{- end -}}

{{- define "estategap.namespace" -}}
{{- $root := .root | default . -}}
{{- $name := .name | default "" -}}
{{- if $name -}}
{{- $service := index $root.Values.services $name -}}
{{- default "estategap-system" $service.namespace -}}
{{- else -}}
{{- default $root.Release.Namespace $root.Values.cluster.namespace -}}
{{- end -}}
{{- end -}}

{{- define "estategap.serviceImage" -}}
{{- $root := .root | default . -}}
{{- $image := .image -}}
{{- $registry := trimSuffix "/" (default "" $root.Values.global.imageRegistry) -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $image.repository $image.tag -}}
{{- else -}}
{{- printf "%s:%s" $image.repository $image.tag -}}
{{- end -}}
{{- end -}}

{{- define "estategap.serviceLabels" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{ include "estategap.labels" $root }}
app.kubernetes.io/component: {{ $name }}
{{- end -}}

{{- define "estategap.serviceSelectorLabels" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{ include "estategap.selectorLabels" $root }}
app.kubernetes.io/component: {{ $name }}
{{- end -}}

{{- define "estategap.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "estategap.commonEnv" -}}
- name: CLUSTER_ENVIRONMENT
  value: {{ .Values.cluster.environment | quote }}
- name: DATABASE_HOST
  value: estategap-postgres-rw.estategap-system.svc.cluster.local
- name: DATABASE_RO_HOST
  value: estategap-postgres-r.estategap-system.svc.cluster.local
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_NAME
  value: {{ .Values.postgresql.database | quote }}
- name: REDIS_HOST
  value: redis.estategap-system.svc.cluster.local
- name: REDIS_PORT
  value: "6379"
- name: REDIS_SENTINEL_HOST
  value: redis.estategap-system.svc.cluster.local
- name: REDIS_SENTINEL_PORT
  value: "26379"
- name: NATS_URL
  value: nats://nats.estategap-system.svc.cluster.local:4222
- name: MINIO_ENDPOINT
  value: http://minio.estategap-system.svc.cluster.local:9000
- name: MINIO_BUCKET_ML_MODELS
  value: {{ index .Values.minio.buckets 0 | quote }}
- name: MINIO_BUCKET_TRAINING_DATA
  value: {{ index .Values.minio.buckets 1 | quote }}
- name: MINIO_BUCKET_LISTING_PHOTOS
  value: {{ index .Values.minio.buckets 2 | quote }}
- name: MINIO_BUCKET_EXPORTS
  value: {{ index .Values.minio.buckets 3 | quote }}
- name: MINIO_BUCKET_BACKUPS
  value: {{ index .Values.minio.buckets 4 | quote }}
{{- if and .Values.testMode .Values.testMode.enabled }}
- name: ESTATEGAP_TEST_MODE
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: ESTATEGAP_TEST_MODE
- name: NOW_OVERRIDE
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: NOW_OVERRIDE
- name: FAKE_LLM_PROVIDER
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: FAKE_LLM_PROVIDER
- name: TEST_SCHEDULE_OVERRIDE
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: TEST_SCHEDULE_OVERRIDE
- name: FIXTURE_MINIO_BUCKET
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: FIXTURE_MINIO_BUCKET
{{- end }}
{{- end -}}

{{- define "estategap.serviceDeployment" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $port := .port -}}
{{- $service := index $root.Values.services $name -}}
{{- $replicas := default 1 $service.replicaCount -}}
{{- if and $service.hpa $service.hpa.enabled -}}
{{- $replicas = int $service.hpa.minReplicas -}}
{{- end }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  namespace: {{ include "estategap.namespace" (dict "root" $root "name" $name) }}
  labels:
    {{- include "estategap.serviceLabels" (dict "root" $root "name" $name) | nindent 4 }}
spec:
  replicas: {{ $replicas }}
  selector:
    matchLabels:
      {{- include "estategap.serviceSelectorLabels" (dict "root" $root "name" $name) | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "estategap.serviceSelectorLabels" (dict "root" $root "name" $name) | nindent 8 }}
        app.kubernetes.io/scrape: "true"
    spec:
      {{- include "estategap.imagePullSecrets" $root | nindent 6 }}
      containers:
        - name: {{ $name }}
          image: {{ include "estategap.serviceImage" (dict "root" $root "image" $service.image) }}
          imagePullPolicy: IfNotPresent
          {{- if $service.command }}
          command:
            {{- toYaml $service.command | nindent 12 }}
          {{- end }}
          ports:
            - name: http
              containerPort: {{ $port }}
              protocol: TCP
          env:
            {{- include "estategap.commonEnv" $root | nindent 12 }}
            {{- range $envName, $envSpec := $service.env }}
            - name: {{ $envName }}
              {{- if hasKey $envSpec "value" }}
              value: {{ $envSpec.value | quote }}
              {{- end }}
              {{- if hasKey $envSpec "valueFrom" }}
              valueFrom:
                {{- toYaml $envSpec.valueFrom | nindent 16 }}
              {{- end }}
            {{- end }}
          resources:
            {{- toYaml $service.resources | nindent 12 }}
{{- end -}}

{{- define "estategap.serviceService" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $port := .port -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ $name }}
  namespace: {{ include "estategap.namespace" (dict "root" $root "name" $name) }}
  labels:
    {{- include "estategap.serviceLabels" (dict "root" $root "name" $name) | nindent 4 }}
spec:
  type: ClusterIP
  selector:
    {{- include "estategap.serviceSelectorLabels" (dict "root" $root "name" $name) | nindent 4 }}
  ports:
    - name: http
      port: {{ $port }}
      targetPort: http
      protocol: TCP
{{- end -}}

{{- define "estategap.serviceHPA" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $service := index $root.Values.services $name -}}
{{- if and $service.hpa $service.hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ $name }}-hpa
  namespace: {{ include "estategap.namespace" (dict "root" $root "name" $name) }}
  labels:
    {{- include "estategap.serviceLabels" (dict "root" $root "name" $name) | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ $name }}
  minReplicas: {{ $service.hpa.minReplicas }}
  maxReplicas: {{ $service.hpa.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $service.hpa.cpuTarget }}
{{- end }}
{{- end -}}
