package models

import "github.com/shopspring/decimal"

func init() {
	decimal.MarshalJSONWithoutQuotes = true
}
