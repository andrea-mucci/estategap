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

{{- define "estategap.serviceMonitorPort" -}}
{{- if hasKey .service "metricsPort" -}}
metrics
{{- else -}}
http
{{- end -}}
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
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_HOST
- name: DATABASE_PORT
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_PORT
- name: DATABASE_NAME
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_NAME
- name: DATABASE_SSLMODE
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_SSLMODE
{{- if .Values.postgresql.readReplica.enabled }}
- name: DATABASE_RO_HOST
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_RO_HOST
- name: DATABASE_RO_PORT
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: DATABASE_RO_PORT
{{- end }}
- name: REDIS_HOST
  value: redis.estategap-system.svc.cluster.local
- name: REDIS_PORT
  value: "6379"
- name: REDIS_SENTINEL_HOST
  value: redis.estategap-system.svc.cluster.local
- name: REDIS_SENTINEL_PORT
  value: "26379"
{{ include "estategap.kafkaEnv" . }}
{{ include "estategap.s3Env" . }}
{{ include "estategap.s3CredentialEnv" . }}
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
- name: FIXTURE_S3_BUCKET
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: FIXTURE_S3_BUCKET
{{- end }}
{{- end -}}

{{- define "estategap.s3Env" -}}
- name: S3_ENDPOINT
  value: {{ .Values.s3.endpoint | quote }}
- name: S3_REGION
  value: {{ .Values.s3.region | quote }}
- name: S3_BUCKET_PREFIX
  value: {{ .Values.s3.bucketPrefix | quote }}
{{- if and .Values.testMode .Values.testMode.enabled }}
- name: FIXTURE_S3_BUCKET
  valueFrom:
    configMapKeyRef:
      name: estategap-config
      key: FIXTURE_S3_BUCKET
{{- end }}
{{- end -}}

{{- define "estategap.s3CredentialEnv" -}}
- name: S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.s3.credentialsSecret | quote }}
      key: AWS_ACCESS_KEY_ID
- name: S3_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.s3.credentialsSecret | quote }}
      key: AWS_SECRET_ACCESS_KEY
{{- end -}}

{{- define "estategap.kafkaEnv" -}}
- name: KAFKA_BROKERS
  valueFrom:
    configMapKeyRef:
      name: estategap-kafka-config
      key: KAFKA_BROKERS
- name: KAFKA_TOPIC_PREFIX
  valueFrom:
    configMapKeyRef:
      name: estategap-kafka-config
      key: KAFKA_TOPIC_PREFIX
- name: KAFKA_TLS_ENABLED
  valueFrom:
    configMapKeyRef:
      name: estategap-kafka-config
      key: KAFKA_TLS_ENABLED
- name: KAFKA_MAX_RETRIES
  valueFrom:
    configMapKeyRef:
      name: estategap-kafka-config
      key: KAFKA_MAX_RETRIES
{{- if .Values.kafka.sasl.enabled }}
- name: KAFKA_SASL_MECHANISM
  valueFrom:
    configMapKeyRef:
      name: estategap-kafka-config
      key: KAFKA_SASL_MECHANISM
- name: KAFKA_SASL_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ .Values.kafka.sasl.credentialsSecret | quote }}
      key: KAFKA_SASL_USERNAME
- name: KAFKA_SASL_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.kafka.sasl.credentialsSecret | quote }}
      key: KAFKA_SASL_PASSWORD
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
