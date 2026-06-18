import ExcelJS from "exceljs";
import type { ProcessedFile } from "./types";

const HEADER_FILL = "FF15578F"; // TRB blue
const HEADER_FONT = "FFFFFFFF";

function styleHeader(row: ExcelJS.Row) {
  row.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: HEADER_FONT } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: HEADER_FILL } };
    cell.alignment = { vertical: "middle" };
  });
}

/**
 * Build a two-sheet .xlsx from the extracted (and possibly user-corrected) results
 * and trigger a browser download. Only completed documents are exported.
 */
export async function exportToExcel(files: ProcessedFile[]): Promise<void> {
  const done = files.filter((f) => f.status === "done" && f.data);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "TRB AI Order Extraction";
  workbook.created = new Date();

  // ---- Sheet 1: Orders (one row per document) ----
  const orders = workbook.addWorksheet("Orders");
  orders.columns = [
    { header: "File Name", key: "fileName", width: 28 },
    { header: "Customer Name", key: "customer", width: 26 },
    { header: "Document Number", key: "docNumber", width: 18 },
    { header: "Supplier Code", key: "supplier", width: 16 },
    { header: "Delivery Address", key: "address", width: 36 },
    { header: "Country", key: "country", width: 14 },
    { header: "Delivery Date", key: "deliveryDate", width: 16 },
    { header: "Payment Terms (days)", key: "paymentTerms", width: 20 },
    { header: "Currency", key: "currency", width: 12 },
    { header: "Confidence", key: "confidence", width: 12 },
    { header: "Comments", key: "comments", width: 44 },
  ];
  styleHeader(orders.getRow(1));

  for (const f of done) {
    const d = f.data!;
    orders.addRow({
      fileName: f.fileName,
      customer: d.customer_name ?? "",
      docNumber: d.document_number ?? "",
      supplier: d.supplier_code ?? "",
      address: d.delivery_address ?? "",
      country: d.country ?? "",
      deliveryDate: d.requested_delivery_date ?? "",
      paymentTerms: d.payment_terms_days ?? "",
      currency: d.currency ?? "",
      confidence: `${Math.round(d.confidence * 100)}%`,
      comments: d.comments ?? "",
    });
  }

  // ---- Sheet 2: Order Lines (one row per product) ----
  const lines = workbook.addWorksheet("Order Lines");
  lines.columns = [
    { header: "File Name", key: "fileName", width: 28 },
    { header: "Document Number", key: "docNumber", width: 18 },
    { header: "Product Name", key: "product", width: 36 },
    { header: "SKU", key: "sku", width: 14 },
    { header: "Quantity", key: "quantity", width: 12 },
    { header: "Unit Price", key: "unitPrice", width: 14 },
    { header: "Currency", key: "currency", width: 12 },
  ];
  styleHeader(lines.getRow(1));

  for (const f of done) {
    const d = f.data!;
    for (const p of d.products) {
      lines.addRow({
        fileName: f.fileName,
        docNumber: d.document_number ?? "",
        product: p.product_name ?? "",
        sku: p.sku ?? "",
        quantity: p.quantity ?? "",
        unitPrice: p.unit_price ?? "",
        currency: p.currency ?? d.currency ?? "",
      });
    }
  }

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `TRB-orders-${stamp}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
