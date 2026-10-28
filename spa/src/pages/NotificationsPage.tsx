import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Notification } from "../api/types";

export function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listNotifications()
      .then((r) => setItems(r.notifications))
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function markRead(id: number) {
    try {
      await api.markNotificationRead(id);
      load();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  return (
    <div className="card">
      <h2>Notifications</h2>
      {error && <div className="notice err">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted">No notifications.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Message</th>
              <th>When</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((n) => (
              <tr key={n.NotificationId} style={{ opacity: n.ReadAt ? 0.55 : 1 }}>
                <td>{n.Message}</td>
                <td className="muted">{new Date(n.CreatedAt).toLocaleString()}</td>
                <td>
                  {n.ReadAt ? (
                    <span className="muted">read</span>
                  ) : (
                    <button className="btn secondary" onClick={() => markRead(n.NotificationId)}>
                      Mark read
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
