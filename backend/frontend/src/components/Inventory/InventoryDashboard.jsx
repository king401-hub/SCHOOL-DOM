import { formatDate } from "../../AppShared";
import { formatMoney } from "./inventoryHelpers";

export default function InventoryDashboard({ data, onRetry }) {
  const stats = data?.stats || {};
  const recentlyAdded = data?.recently_added || [];
  const recentActivity = data?.recent_activity || [];
  const lowStockItems = data?.low_stock_items || [];

  return (
    <div className="inventory-dashboard">
      <div className="inventory-stats">
        <div className="inventory-stat-card">
          <div className="stat-value">{stats.total_items ?? 0}</div>
          <div className="stat-label">Total Inventory Items</div>
        </div>
        <div className="inventory-stat-card">
          <div className="stat-value">{formatMoney(stats.total_stock_value)}</div>
          <div className="stat-label">Total Stock Value</div>
        </div>
        <div className="inventory-stat-card warning">
          <div className="stat-value">{stats.low_stock_count ?? 0}</div>
          <div className="stat-label">Low Stock Items</div>
        </div>
        <div className="inventory-stat-card danger">
          <div className="stat-value">{stats.out_of_stock_count ?? 0}</div>
          <div className="stat-label">Out of Stock Items</div>
        </div>
        <div className="inventory-stat-card">
          <div className="stat-value">{stats.borrowed_count ?? 0}</div>
          <div className="stat-label">Borrowed Items</div>
        </div>
        <div className="inventory-stat-card danger">
          <div className="stat-value">{stats.overdue_count ?? 0}</div>
          <div className="stat-label">Overdue Returns</div>
        </div>
        <div className="inventory-stat-card warning">
          <div className="stat-value">{stats.damaged_count ?? 0}</div>
          <div className="stat-label">Damaged Items</div>
        </div>
      </div>

      <div className="expense-workspace">
        <article className="app-panel">
          <div className="expense-panel-head">
            <h3>Recently Added Items</h3>
            <button type="button" className="table-action" onClick={onRetry}>Refresh</button>
          </div>
          {recentlyAdded.length === 0 ? (
            <p>No items added yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Inventory ID</th><th>Name</th><th>Category</th><th>Qty</th><th>Added</th></tr>
              </thead>
              <tbody>
                {recentlyAdded.map((item) => (
                  <tr key={item.id}>
                    <td>{item.inventory_id}</td>
                    <td>{item.name}</td>
                    <td>{item.category}</td>
                    <td>{item.quantity}</td>
                    <td>{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </article>

        <article className="app-panel">
          <div className="expense-panel-head">
            <h3>Recent Inventory Activity</h3>
          </div>
          {recentActivity.length === 0 ? (
            <p>No activity recorded yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Action</th><th>Item</th><th>Details</th><th>Actor</th><th>Date</th></tr>
              </thead>
              <tbody>
                {recentActivity.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.action.replace(/_/g, " ")}</td>
                    <td>{entry.item_inventory_id || "-"}</td>
                    <td>{entry.description}</td>
                    <td>{entry.actor_name}</td>
                    <td>{formatDate(entry.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </article>
      </div>

      {lowStockItems.length > 0 ? (
        <article className="app-panel">
          <div className="expense-panel-head">
            <h3>Items Needing Reorder</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr><th>Inventory ID</th><th>Name</th><th>Available</th><th>Reorder Level</th></tr>
            </thead>
            <tbody>
              {lowStockItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.inventory_id}</td>
                  <td>{item.name}</td>
                  <td>{item.quantity_available}</td>
                  <td>{item.reorder_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      ) : null}
    </div>
  );
}
