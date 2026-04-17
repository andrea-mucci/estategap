import { beforeEach, describe, expect, it } from "vitest";

import { useNotificationStore } from "./notificationStore";

describe("notificationStore", () => {
  beforeEach(() => {
    useNotificationStore.setState({
      alerts: [],
      toastQueue: [],
      unreadCount: 0,
    });
  });

  it("increments unread count when an alert is added", () => {
    useNotificationStore.getState().addAlert({
      eventId: "evt-1",
      listingId: "listing-1",
      title: "Madrid centre apartment",
      address: "Madrid",
      priceEur: 320000,
      areaM2: 82,
      dealScore: 91,
      dealTier: 1,
      ruleName: "Madrid under 350k",
      triggeredAt: "2026-04-17T00:00:00Z",
      read: false,
    });

    expect(useNotificationStore.getState().alerts).toHaveLength(1);
    expect(useNotificationStore.getState().unreadCount).toBe(1);
  });

  it("decrements unread count when an alert is marked as read", () => {
    useNotificationStore.getState().addAlert({
      eventId: "evt-2",
      listingId: "listing-2",
      title: "Lisbon loft",
      address: "Lisbon",
      priceEur: 410000,
      areaM2: 90,
      dealScore: 88,
      dealTier: 2,
      ruleName: "Lisbon lofts",
      triggeredAt: "2026-04-17T00:00:00Z",
      read: false,
    });

    useNotificationStore.getState().markRead("evt-2");

    expect(useNotificationStore.getState().alerts[0].read).toBe(true);
    expect(useNotificationStore.getState().unreadCount).toBe(0);
  });
});
