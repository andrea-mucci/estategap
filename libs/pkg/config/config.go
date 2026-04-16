package config

import (
	"github.com/spf13/viper"
)

// Load returns a viper instance configured to read environment variables
// with the given prefix and an optional Kubernetes ConfigMap mount path.
func Load(prefix string) (*viper.Viper, error) {
	v := viper.New()
	v.SetEnvPrefix(prefix)
	v.AutomaticEnv()

	// Support Kubernetes ConfigMap mount if specified.
	configPath := v.GetString("CONFIG_PATH")
	if configPath != "" {
		v.SetConfigType("yaml")
		v.AddConfigPath(configPath)
		if err := v.MergeInConfig(); err != nil {
			return nil, err
		}
	}

	return v, nil
}
