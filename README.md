# mini-utilities
Mini applications to solve some problems.

## Python PDF Modifier

This script provides a set of functions for modifying and manipulating PDF files using the `pypdf` library. It's designed to handle a few simple tasks such as duplicating pages, adding custom margins, merging documents, and resizing pages to standard paper sizes.

### Features

* **Duplicate Pages:** Quickly create a new PDF where each page of the original document is duplicated.

* **Add Note-taking Margins:** Add a custom-sized margin to the side of each page. The script automatically calculates the new page size to maintain the original aspect ratio and can optionally use a background PDF (e.g., grid paper) for the margin area.

* **Merge Pages Side-by-Side:** Combine two different PDFs, placing the pages side-by-side onto a new, landscape-oriented page.

* **Resize PDF:** Force a PDF to a specific paper size (e.g., A4, Letter, Tabloid), scaling the content to fit the new dimensions while preserving its aspect ratio.

### Requirements

The dependency for this script is the `pypdf` library. 

### How to Use

The script's functionality is centralized in a single `modify_pdf` function, which dispatches to the correct action based on the `action` argument you provide.

The parameters for each specific action that `modify_pdf` will handle are as follows:

### `action='duplicate'`
* **`input_pdf_path`** (string): The file path of the PDF you want to modify.
* **`output_pdf_path`** (string): The file path where the new, duplicated PDF will be saved.

### `action='add_notes'`
* **`input_pdf_path`** (string): The file path of the source PDF.
* **`output_pdf_path`** (string): The file path for the new PDF with added margins.
* **`background_pdf_path`** (string, optional): The path to a single-page PDF to be used as a background for the notes area. If not provided, the margin will be blank.
* **`margin_proportion`** (float, optional): A number between `0` and `1` that determines the width of the notes margin as a proportion of the page width. Defaults to `0.5` (50% of the page).

### `action='merge_side_by_side'`
* **`input_pdf_path`** (string): The file path of the PDF on the left side.
* **`output_pdf_path`** (string): The file path where the merged PDF will be saved.
* **`merge_pdf_path`** (string): The file path of the PDF on the right side.

### `action='resize'`
* **`input_pdf_path`** (string): The file path of the PDF you want to resize.
* **`output_pdf_path`** (string): The file path for the new, resized PDF.
* **`target_size`** (string, optional): The name of the paper size from the `PAPER_SIZES` dictionary (e.g., `'Letter'`, `'A4'`). Defaults to `'A4'`.
    *  The available paper sizes are:
        *  A0, A1, A2, A3, A4, A5, A6
        *   B0, B1, B2, B3, B4, B5
        *  C0, C1, C2, C3, C4, C5, C6
        *    Letter, Legal, Tabloid


