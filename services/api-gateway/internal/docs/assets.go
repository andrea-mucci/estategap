package docs

import (
	"embed"
	"encoding/json"
	"io/fs"

	"gopkg.in/yaml.v3"
)

//go:embed swagger-ui/* openapi.yaml
var embeddedFiles embed.FS

var (
	swaggerUIFS fs.FS
	openAPIJSON []byte
)

func init() {
	var err error
	swaggerUIFS, err = fs.Sub(embeddedFiles, "swagger-ui")
	if err != nil {
		panic(err)
	}

	specYAML, err := embeddedFiles.ReadFile("openapi.yaml")
	if err != nil {
		panic(err)
	}

	var parsed any
	if err := yaml.Unmarshal(specYAML, &parsed); err != nil {
		panic(err)
	}
	openAPIJSON, err = json.Marshal(parsed)
	if err != nil {
		panic(err)
	}
}

func SwaggerUIFS() fs.FS {
	return swaggerUIFS
}

func OpenAPIJSON() []byte {
	return append([]byte(nil), openAPIJSON...)
}
