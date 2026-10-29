import { jsPDF } from "jspdf";
import type { OrderRecord } from "./api/types";
import { money } from "./format";

// A6: render the confirmed order document to a PDF. Driven ENTIRELY by the one
// persisted OrderRecord the server returns, so the distributor and the engineer
// generate a byte-equivalent document (same inputs -> same layout).
export function downloadOrderPdf(order: OrderRecord): void {
  const d = order.document;
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const left = 48;
  let y = 56;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Order Confirmation", left, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  y += 22;
  doc.text(`CPQ Order: ${order.cpq_order_number}`, left, y);
  doc.text(`Quote: ${d.quote_number ?? "—"}`, left + 240, y);
  y += 16;
  doc.text(`Customer: ${d.customer_name ?? "—"}`, left, y);
  doc.text(`Brand/Site: ${d.brand} / ${d.responsible_site_code}`, left + 240, y);
  y += 16;
  doc.text(`Revision: ${d.revision_no}`, left, y);
  doc.text(
    `Lead time: ${d.lead_time_days != null ? `${d.lead_time_days} days` : "—"}`,
    left + 240,
    y,
  );
  y += 24;

  // U4: contact + ship-to blocks (rendered only when present on the order).
  const partyLines = (p: NonNullable<typeof d.contact>): string[] => {
    const name = [p.first_name, p.last_name].filter(Boolean).join(" ");
    const cityLine = [p.city, p.state, p.postal_code].filter(Boolean).join(", ");
    return [
      p.company_name || "",
      name,
      p.address1 || "",
      p.address2 || "",
      cityLine,
      p.country || "",
      p.phone ? `Tel: ${p.phone}` : "",
      p.email || "",
    ].filter(Boolean);
  };
  if (d.contact || d.ship_to) {
    const blockTop = y;
    doc.setFont("helvetica", "bold");
    if (d.contact) doc.text("Contact", left, y);
    if (d.ship_to) doc.text("Ship to", left + 240, y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    let yC = y + 14;
    for (const ln of d.contact ? partyLines(d.contact) : []) {
      doc.text(String(ln).slice(0, 48), left, yC);
      yC += 12;
    }
    let yS = blockTop + 14;
    for (const ln of d.ship_to ? partyLines(d.ship_to) : []) {
      doc.text(String(ln).slice(0, 48), left + 240, yS);
      yS += 12;
    }
    doc.setFontSize(10);
    y = Math.max(yC, yS) + 10;
  }

  // Lines table (manual, deterministic — no autotable dependency).
  doc.setFont("helvetica", "bold");
  doc.text("#", left, y);
  doc.text("Part number", left + 24, y);
  doc.text("Qty", left + 300, y);
  doc.text("Unit", left + 360, y);
  doc.text("Extended", left + 440, y);
  doc.setFont("helvetica", "normal");
  y += 6;
  doc.line(left, y, left + 520, y);
  y += 14;

  for (const l of d.lines) {
    doc.text(String(l.line_number), left, y);
    doc.text(String(l.part_number ?? "—").slice(0, 44), left + 24, y);
    doc.text(String(l.quantity), left + 300, y);
    doc.text(l.priced ? money(l.unit_price, d.currency) : "C/F", left + 360, y);
    doc.text(l.priced ? money(l.extended_price, d.currency) : "C/F", left + 440, y);
    y += 14;
    if (l.custom_spec) {
      doc.setFontSize(8);
      doc.setTextColor(120);
      doc.text(`   custom: ${l.custom_spec}`.slice(0, 90), left + 24, y);
      doc.setTextColor(0);
      doc.setFontSize(10);
      y += 13;
    }
    if (y > 700) {
      doc.addPage();
      y = 56;
    }
  }

  y += 6;
  doc.line(left + 300, y, left + 520, y);
  y += 16;
  doc.text("Merchandise subtotal", left + 300, y);
  doc.text(money(d.merchandise_subtotal, d.currency), left + 440, y);
  y += 15;
  doc.text(
    `Loyalty discount${d.loyalty_tier_code ? ` (${d.loyalty_tier_code})` : ""}`,
    left + 300,
    y,
  );
  doc.text(
    (d.discount_amount > 0 ? "-" : "") + money(d.discount_amount, d.currency),
    left + 440,
    y,
  );
  y += 15;
  doc.setFont("helvetica", "bold");
  doc.text("Net total", left + 300, y);
  doc.text(money(d.net_total, d.currency), left + 440, y);
  doc.setFont("helvetica", "normal");

  doc.save(`${order.cpq_order_number}.pdf`);
}
