import { useState } from "react";
import { ScreenState } from "../../AppShared";
import "./Inventory.css";
import InventoryDashboard from "./InventoryDashboard";
import InventoryItemsPanel from "./InventoryItemsPanel";
import StockMovementsPanel from "./StockMovementsPanel";
import BorrowingPanel from "./BorrowingPanel";
import AuditLogPanel from "./AuditLogPanel";

const TABS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "items", label: "Items" },
  { key: "stock", label: "Stock Movements" },
  { key: "borrowing", label: "Borrowing" },
  { key: "audit", label: "Audit Log" },
];

export default function InventoryScreen({ data, loading, error, onRetry, session }) {
  const [activeTab, setActiveTab] = useState("dashboard");

  return (
    <section className="screen-grid inventory-screen">
      <div className="screen-hero">
        <div>
          <h2>Inventory Management</h2>
          <p>Track furniture, ICT equipment, lab/library resources, and every other physical asset from one place.</p>
        </div>
      </div>

      <ScreenState loading={loading && !data} error={error} onRetry={onRetry} />

      <div className="table-actions-inline inventory-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`table-action${activeTab === tab.key ? " active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "dashboard" ? (
        <InventoryDashboard data={data} onRetry={onRetry} />
      ) : activeTab === "items" ? (
        <InventoryItemsPanel session={session} />
      ) : activeTab === "stock" ? (
        <StockMovementsPanel session={session} />
      ) : activeTab === "borrowing" ? (
        <BorrowingPanel session={session} />
      ) : (
        <AuditLogPanel session={session} />
      )}
    </section>
  );
}
