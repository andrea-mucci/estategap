package templates

import "embed"

// FS exposes embedded email templates to sender packages.
//
//go:embed *.html
var FS embed.FS
