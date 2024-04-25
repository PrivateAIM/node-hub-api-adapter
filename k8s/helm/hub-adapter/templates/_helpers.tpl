{{/*
Create a default fully qualified app name.
Truncated at 63 chars because some k8s name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "common.names.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Return the secret containing the Keycloak client secret
*/}}
{{- define "adapter.keycloak.secretName" -}}
{{- $secretName := .Values.idp.existingSecret -}}
{{- if and $secretName ( not .Values.idp.debug ) -}}
    {{- printf "%s" (tpl $secretName $) -}}
{{- else -}}
    {{- printf "%s-hub-adapter-keycloak-secret" .Release.Name -}}
{{- end -}}
{{- end -}}

{{/*
Return the secret key that contains the Keycloak client secret
*/}}
{{- define "adapter.keycloak.secretKey" -}}
{{- $secretName := .Values.idp.existingSecret -}}
{{- if .Values.idp.debug -}}
    {{- print "static" -}}
{{- else if and $secretName .Values.idp.existingSecretKey -}}
    {{- printf "%s" .Values.idp.existingSecretKey -}}
{{- else -}}
    {{- print "hub-adapter-kc-secret" -}}
{{- end -}}
{{- end -}}

{{/*
Return the Keycloak endpoint
*/}}
{{- define "adapter.keycloak.endpoint" -}}
{{- if .Values.idp.host -}}
    {{- .Values.idp.host -}}
{{- else -}}
    {{- printf "http://%s-keycloak-headless:8080" .Release.Name -}}
{{- end -}}
{{- end -}}

{{/*
Return the Results service endpoint
*/}}
{{- define "adapter.results.endpoint" -}}
{{- if .Values.node.results -}}
    {{- .Values.node.results -}}
{{- else -}}
    {{- printf "http://%s-node-result-service:8080" .Release.Name -}}
{{- end -}}
{{- end -}}

{{/*
Return the Kong admin service endpoint
*/}}
{{- define "adapter.kong.endpoint" -}}
{{- if .Values.node.kong -}}
    {{- .Values.node.kong -}}
{{- else -}}
    {{- printf "http://%s-kong-service:8000" .Release.Name -}}
{{- end -}}
{{- end -}}

{{/*
Return the Pod Orchestrator endpoint
*/}}
{{- define "adapter.po.endpoint" -}}
{{- if .Values.node.po -}}
    {{- .Values.node.po -}}
{{- else -}}
    {{- printf "http://%s-po-service:8000" .Release.Name -}}
{{- end -}}
{{- end -}}
