package pool

import "sync"

type HealthWindow struct {
	mu        sync.RWMutex
	results   [100]bool
	head      int
	count     int
	successes int
}

func (h *HealthWindow) Record(success bool) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if h.count == len(h.results) {
		if h.results[h.head] {
			h.successes--
		}
	} else {
		h.count++
	}

	h.results[h.head] = success
	if success {
		h.successes++
	}
	h.head = (h.head + 1) % len(h.results)
}

func (h *HealthWindow) Score() float64 {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if h.count == 0 {
		return 1.0
	}
	return float64(h.successes) / float64(h.count)
}
