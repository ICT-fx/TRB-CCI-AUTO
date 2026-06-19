import ExcelJS from "exceljs";
import type { ProcessedFile } from "./types";

const HEADER_FILL = "FF15578F"; // TRB blue
const HEADER_FONT = "FFFFFFFF";

interface Column {
  header: string;
  key: string;
  width: number;
}

// Document-level columns (one value per order).
const DOC_COLUMNS: Column[] = [
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

/**
 * Export every completed (and possibly user-corrected) order to a SINGLE sheet,
 * ONE ROW PER ORDER. All product lines are spread across columns
 * (Product 1 …, Product 2 …, etc.), so each order is fully contained on one row.
 */
export async function exportToExcel(files: ProcessedFile[]): Promise<void> {
  const done = files.filter((f) => f.status === "done" && f.data);

  // Widest order determines how many product column groups we need.
  const maxProducts = done.reduce(
    (max, f) => Math.max(max, f.data!.products.length),
    0,
  );

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "TRB AI Order Extraction";
  workbook.created = new Date();

  const sheet = workbook.addWorksheet("Orders");

  // Build the dynamic column set: document columns + N product groups.
  const columns: Column[] = [...DOC_COLUMNS];
  for (let i = 1; i <= maxProducts; i++) {
    columns.push(
      { header: `Product ${i} Name`, key: `p${i}_name`, width: 30 },
      { header: `Product ${i} SKU`, key: `p${i}_sku`, width: 12 },
      { header: `Product ${i} Quantity`, key: `p${i}_qty`, width: 14 },
      { header: `Product ${i} Unit Price`, key: `p${i}_price`, width: 16 },
      { header: `Product ${i} Currency`, key: `p${i}_currency`, width: 12 },
    );
  }
  sheet.columns = columns;

  // Style + freeze the header row.
  const headerRow = sheet.getRow(1);
  headerRow.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: HEADER_FONT } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: HEADER_FILL } };
    cell.alignment = { vertical: "middle" };
  });
  sheet.views = [{ state: "frozen", ySplit: 1 }];

  for (const f of done) {
    const d = f.data!;
    const row: Record<string, string | number> = {
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
    };

    d.products.forEach((p, idx) => {
      const i = idx + 1;
      row[`p${i}_name`] = p.product_name ?? "";
      row[`p${i}_sku`] = p.sku ?? "";
      row[`p${i}_qty`] = p.quantity ?? "";
      row[`p${i}_price`] = p.unit_price ?? "";
      row[`p${i}_currency`] = p.currency ?? d.currency ?? "";
    });

    sheet.addRow(row);
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
