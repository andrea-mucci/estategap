# Helm Values

## S3 Object Storage

| Field | Type | Default | Description |
|---|---|---|---|
| `s3.endpoint` | `string` | `https://fsn1.your-objectstorage.com` | S3-compatible object storage endpoint used by services and CNPG backups. |
| `s3.region` | `string` | `fsn1` | Object storage region identifier. |
| `s3.bucketPrefix` | `string` | `estategap` | Prefix applied to every logical bucket name. |
| `s3.forcePathStyle` | `bool` | `true` | Enables path-style S3 addressing for Hetzner Object Storage. |
| `s3.credentials.secret` | `string` | `estategap-s3-credentials` | Namespace-local secret name that stores S3 access credentials. |
| `s3.buckets.mlModels` | `string` | `ml-models` | Logical suffix for model artifact storage. |
| `s3.buckets.trainingData` | `string` | `training-data` | Logical suffix for training dataset storage. |
| `s3.buckets.listingPhotos` | `string` | `listing-photos` | Logical suffix for listing photo storage. |
| `s3.buckets.exports` | `string` | `exports` | Logical suffix for GDPR export archive storage. |
| `s3.buckets.backups` | `string` | `backups` | Logical suffix for PostgreSQL backup storage. |
