package ctxkey

import "context"

type key string

var (
	UserID    = key("user_id")
	UserEmail = key("user_email")
	UserTier  = key("user_tier")
	RequestID = key("request_id")
	JTI       = key("jwt_id")
)

func String(ctx context.Context, k any) string {
	value, _ := ctx.Value(k).(string)
	return value
}
