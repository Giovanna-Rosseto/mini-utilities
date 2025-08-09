# mini-utilities
Mini applications to solve some problems.

## Python PDF Modifier

This script provides a set of functions for modifying and manipulating PDF files using the `pypdf` library. It's designed to handle a few simple tasks, now with the added ability to chain multiple actions together and run them in a separate process.

## Features

* **Chained Actions:** You can apply a sequence of modifications (e.g., duplicate pages and then resize them) by providing a list of actions.

* **Multiprocessing:** The `run_in_separate_process` method allows the modification to run in a separate process, preventing the main program from freezing during long operations.

* **File Compression:** A `compress_output` option can be used to re-save the final PDF, which may help to reduce the file size.

* **Duplicate Pages:** Quickly create a new PDF where each page of the original document is duplicated.

* **Add Note-taking Margins:** Add a custom-sized margin to the side of each page. The script automatically calculates the new page size to maintain the original aspect ratio and can optionally use a background PDF (e.g., grid paper) for the margin area.

* **Merge Pages Side-by-Side:** Combine two different PDFs, placing the pages side-by-side onto a new, landscape-oriented page.

* **Resize PDF:** Force a PDF to a specific paper size (e.g., A4, Letter, Tabloid), scaling the content to fit the new dimensions while preserving its aspect ratio. The available sizes now include landscape versions.

## Requirements

The dependency for this script is the `pypdf` library.

## How to Use

The script's functionality is centralized in the `PDFModifier` class. You can create an instance of this class with the desired parameters and then call either `modify_pdf()` for synchronous execution or `run_in_separate_process()` for non-blocking execution.

### Parameters for `PDFModifier`

* **`input_pdf_path`** (string): The file path of the PDF you want to modify.

* **`output_pdf_path`** (string): The file path where the new PDF will be saved.

* **`action`** (string or list): The name(s) of the modification function to call. Can be a single string or a list of strings for chained actions. Supported actions are: `'duplicate'`, `'add_notes'`, `'merge_side_by_side'`, `'resize'`.

* **`background_pdf_path`** (string, optional): The path to a single-page PDF to be used as a background for the notes area. Used with `'add_notes'`.

* **`margin_proportion`** (float, optional): A number between 0 and 1 that determines the width of the notes margin as a proportion of the page width. Defaults to `0.5`. Used with `'add_notes'`.

* **`merge_pdf_path`** (string): The file path of the PDF to merge. Used with `'merge_side-by-side'`.

* **`target_size`** (string, optional): The name of the paper size from the `PAPER_SIZES` dictionary. Defaults to `'A4'`. Used with `'resize'`.

* **`compress_output`** (boolean, optional): If `True`, the output PDF will be re-saved with compression applied. Defaults to `False`.

### Available Paper Sizes

The `PAPER_SIZES` dictionary includes all standard paper sizes as well as their landscape variants, denoted by `_Landscape`.

* A0, A1, A2, A3, A4, A5, A6

* A0_Landscape, A1_Landscape, A2_Landscape, etc.

* B0, B1, B2, B3, B4, B5

* B0_Landscape, B1_Landscape, B2_Landscape, etc.

* C0, C1, C2, C3, C4, C5, C6

* C0_Landscape, C1_Landscape, C2_Landscape, etc.

* Letter, Legal, Tabloid

* Letter_Landscape, Legal_Landscape, Tabloid_Landscape

