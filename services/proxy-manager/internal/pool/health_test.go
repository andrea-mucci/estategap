package pool

import "testing"

func TestHealthWindowScore(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name     string
		inputs   []bool
		expected float64
	}{
		{name: "fresh window", expected: 1.0},
		{name: "all failures", inputs: repeat(false, 100), expected: 0.0},
		{name: "half success boundary", inputs: append(repeat(true, 50), repeat(false, 50)...), expected: 0.5},
		{name: "score recovery after failures", inputs: append(repeat(false, 100), repeat(true, 100)...), expected: 1.0},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			var window HealthWindow
			for _, input := range tc.inputs {
				window.Record(input)
			}

			if got := window.Score(); got != tc.expected {
				t.Fatalf("Score() = %v, want %v", got, tc.expected)
			}
		})
	}
}

func repeat(value bool, count int) []bool {
	out := make([]bool, count)
	for i := range out {
		out[i] = value
	}
	return out
}
