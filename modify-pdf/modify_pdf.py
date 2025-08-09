import os
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from copy import deepcopy

# Dictionary of standard paper sizes in PostScript points (1/72 of an inch)
# This is kept as a global constant as it is a static lookup table.
PAPER_SIZES = {
    "A0": PaperSize.A0,
    "A1": PaperSize.A1,
    "A2": PaperSize.A2,
    "A3": PaperSize.A3,
    "A4": PaperSize.A4,
    "A5": PaperSize.A5,
    "A6": PaperSize.A6,
    "Letter": (612, 792),  # 8.5 x 11 inches
    "Legal": (612, 1008),  # 8.5 x 14 inches
    "Tabloid": (792, 1224),  # 11 x 17 inches
    # B Series - based on ISO 216 dimensions
    "B0": (1000 / 25.4 * 72, 1414 / 25.4 * 72),
    "B1": (707 / 25.4 * 72, 1000 / 25.4 * 72),
    "B2": (500 / 25.4 * 72, 707 / 25.4 * 72),
    "B3": (353 / 25.4 * 72, 500 / 25.4 * 72),
    "B4": (250 / 25.4 * 72, 353 / 25.4 * 72),
    "B5": (176 / 25.4 * 72, 250 / 25.4 * 72),
    # C Series - based on ISO 216 dimensions for envelopes
    "C0": (917 / 25.4 * 72, 1297 / 25.4 * 72),
    "C1": (648 / 25.4 * 72, 917 / 25.4 * 72),
    "C2": (458 / 25.4 * 72, 648 / 25.4 * 72),
    "C3": (324 / 25.4 * 72, 458 / 25.4 * 72),
    "C4": (229 / 25.4 * 72, 324 / 25.4 * 72),
    "C5": (162 / 25.4 * 72, 229 / 25.4 * 72),
    "C6": (114 / 25.4 * 72, 162 / 25.4 * 72),
}


class PDFModifier:
    """
    A class to handle various PDF modification tasks.
    It encapsulates the logic for different actions like duplicating,
    resizing, and merging PDFs.
    """

    def __init__(self, input_pdf_path=None, output_pdf_path=None, action=None,
                 background_pdf_path=None, margin_proportion=0.5,
                 merge_pdf_path=None, target_size="A4",
                 input_start_page=0, input_end_page=None,
                 append_to_existing=False):
        """
        Initializes the PDFModifier class with all necessary parameters for
        a specific modification task.

        If `output_pdf_path` is not provided, a default path is generated
        by appending '_output' before the file extension of `input_pdf_path`.

        Args:
            input_pdf_path (str, optional): The path to the input PDF file.
            output_pdf_path (str, optional): The path to save the output PDF file.
            action (str): The name of the modification function to call.
                          Supported actions: 'duplicate', 'add_notes',
                          'merge_side_by_side', 'resize'.
            background_pdf_path (str, optional): The path to a background PDF
                                                  for 'add_notes'.
            margin_proportion (float, optional): The proportion of the page
                                                 for the margin in 'add_notes'.
            merge_pdf_path (str, optional): The path to the PDF to merge
                                            for 'merge_side_by_side'.
            target_size (str, optional): The target paper size for 'resize'.
            input_start_page (int, optional): The starting page index (0-based)
                                              for processing. Defaults to 0.
            input_end_page (int, optional): The ending page index (0-based,
                                            exclusive) for processing. Defaults
                                            to the end of the document.
            append_to_existing (bool, optional): If True, appends the new pages
                                                 to an existing output PDF file.
                                                 Defaults to False (overwrite).
        """
        self.input_pdf_path = input_pdf_path

        # If no output path is provided, generate a default one
        if output_pdf_path:
            self.output_pdf_path = output_pdf_path
        elif self.input_pdf_path:
            base, ext = os.path.splitext(self.input_pdf_path)
            self.output_pdf_path = f"{base}_output{ext}"
        else:
            raise ValueError("'input_pdf_path' or 'output_pdf_path' "
                             "must be provided during initialization.")

        # Store all parameters as instance attributes
        self.action = action
        self.background_pdf_path = background_pdf_path
        self.margin_proportion = margin_proportion
        self.merge_pdf_path = merge_pdf_path
        self.target_size = target_size
        self.input_start_page = input_start_page
        self.input_end_page = input_end_page
        self.append_to_existing = append_to_existing

    @staticmethod
    def _verify_paths(*paths):
        """
        Internal helper function to check if all provided file paths exist.
        """
        for path in paths:
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Error: The file '{path}' was not found.")
        return True

    @staticmethod
    def _print_pdf_info(pdf_path, title):
        """
        Internal helper function to print quality metadata for a given PDF.
        This includes page count and the dimensions of the first page.
        """
        if not os.path.exists(pdf_path):
            print(f"File not found: '{pdf_path}'")
            return

        reader = None
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            if num_pages > 0:
                first_page = reader.pages[0]
                width = float(first_page.mediabox.width)
                height = float(first_page.mediabox.height)
                print(f"{title} - File: '{pdf_path}'")
                print(f"    - Page count: {num_pages}")
                print(f"    - First page dimensions: {width:.2f}pt x "
                      f"{height:.2f}pt")
            else:
                print(f"{title} - File: '{pdf_path}' has no pages.")
        except Exception as e:
            print(f"Error reading PDF info for '{pdf_path}': {e}")
        finally:
            if reader:
                reader.close()

    def _duplicate_pages(self, pages_to_process, writer):
        """
        Duplicates each page in a list of PDF pages, showing progress in chunks.
        This is a private method, called only by modify_pdf.
        """
        num_pages = len(pages_to_process)
        if num_pages == 0:
            return

        chunk_size = 10
        print(f"Starting to process {num_pages} pages in chunks of {chunk_size}...")

        for i, page in enumerate(pages_to_process):
            writer.add_page(page)
            writer.add_page(page)
            # Print a message every 10 pages processed.
            if num_pages > chunk_size and (i + 1) % chunk_size == 0 or i == num_pages - 1:
                print(f"Processed {i + 1} of {num_pages} pages.")

        print("\nFinalizing PDF file...")
        with open(self.output_pdf_path, "wb") as output_file:
            writer.write(output_file)
        print("Finalization complete.")

        print(f"Success: The duplicated PDF was saved to "
              f"'{self.output_pdf_path}'.")

    def _add_note_margin(self, pages_to_process, writer):
        """
        Adds a note-taking margin to each page by placing the original page
        on a new page with a user-defined margin proportion, showing progress.
        This is a private method, called only by modify_pdf.
        """
        if not 0 <= self.margin_proportion < 1:
            raise ValueError("Error: 'margin_proportion' must be between "
                             "0 and 1.")

        if len(pages_to_process) == 0:
            return

        chunk_size = 10
        num_pages = len(pages_to_process)
        print(f"Starting to process {num_pages} pages in chunks of {chunk_size}...")

        background_reader = None
        try:
            if self.background_pdf_path:
                self._verify_paths(self.background_pdf_path)
                background_reader = PdfReader(self.background_pdf_path)
                if not background_reader.pages:
                    raise ValueError(
                        f"Error: The background file "
                        f"'{self.background_pdf_path}' has no pages.")

            for i, page in enumerate(pages_to_process):
                page_width = page.mediabox.width
                page_height = page.mediabox.height

                ideal_width = page_width / (1 - self.margin_proportion)
                ideal_height = page_height

                dest_page = writer.add_blank_page(width=ideal_width,
                                                  height=ideal_height)
                dest_page.merge_page(page)

                if background_reader:
                    background_page = background_reader.pages[0]
                    background_page_height = background_page.mediabox.height

                    scale_bg = ideal_height / background_page_height

                    dest_page.merge_transformed_page(
                        background_page,
                        Transformation().scale(scale_bg)
                        .translate(page_width, 0)
                    )
                # Print a message every 10 pages processed.
                if num_pages > chunk_size and (i + 1) % chunk_size == 0 or i == num_pages - 1:
                    print(f"Processed {i + 1} of {num_pages} pages.")

            print("\nFinalizing PDF file...")
            with open(self.output_pdf_path, "wb") as output_file:
                writer.write(output_file)
            print("Finalization complete.")

            print(f"Success: The note-taking PDF was saved to "
                  f"'{self.output_pdf_path}'.")
        finally:
            if background_reader:
                background_reader.close()

    def _merge_pdf_side_by_side(self, pages_to_process, writer):
        """
        Merges each page of a PDF with a page from another PDF, placing them
        side-by-side on a new A4 landscape page, showing progress.
        This is a private method, called only by modify_pdf.
        """
        if len(pages_to_process) == 0:
            return

        chunk_size = 10
        num_pages = len(pages_to_process)
        print(f"Starting to process {num_pages} pages in chunks of {chunk_size}...")

        merge_reader = None
        try:
            self._verify_paths(self.merge_pdf_path)
            merge_reader = PdfReader(self.merge_pdf_path)
            if len(merge_reader.pages) < 1:
                raise ValueError("Error: The merge PDF must contain at least "
                                 "one page.")

            original_merge_page = merge_reader.pages[0]

            width = PaperSize.A4.height
            height = PaperSize.A4.width

            for i, page in enumerate(pages_to_process):
                dest_page = writer.add_blank_page(width=width, height=height)
                merge_page = deepcopy(original_merge_page)

                page_width = page.mediabox.width
                page_height = page.mediabox.height
                x_scale = (width / 2) / page_width
                y_scale = height / page_height
                scale = min(x_scale, y_scale)

                merge_page_width = merge_page.mediabox.width
                merge_page_height = merge_page.mediabox.height
                x_scale_merge = (width / 2) / merge_page_width
                y_scale_merge = height / merge_page_height
                scale_merge = min(x_scale_merge, y_scale_merge)

                dest_page.merge_transformed_page(
                    page,
                    Transformation().scale(scale)
                )

                dest_page.merge_transformed_page(
                    merge_page,
                    Transformation().scale(scale_merge)
                    .translate(width / 2, 0)
                )

                # Print a message every 10 pages processed.
                if num_pages > chunk_size and (i + 1) % chunk_size == 0 or i == num_pages - 1:
                    print(f"Processed {i + 1} of {num_pages} pages.")

            print("\nFinalizing PDF file...")
            with open(self.output_pdf_path, "wb") as output_file:
                writer.write(output_file)
            print("Finalization complete.")

            print(f"Success: The modified PDF was saved to "
                  f"'{self.output_pdf_path}'.")
        finally:
            if merge_reader:
                merge_reader.close()

    def _resize_pdf(self, pages_to_process, writer):
        """
        Resizes each page of a PDF to a specific paper size,
        scaling the content to fit within the new dimensions, showing progress.
        This is a private method, called only by modify_pdf.
        """
        target_dimensions = PAPER_SIZES.get(self.target_size)
        if not target_dimensions:
            raise ValueError(
                f"Error: Invalid target size '{self.target_size}'.\n"
                f"Supported sizes are: {', '.join(PAPER_SIZES.keys())}")

        if len(pages_to_process) == 0:
            return

        chunk_size = 10
        target_width, target_height = target_dimensions
        num_pages = len(pages_to_process)
        print(f"Starting to process {num_pages} pages in chunks of {chunk_size}...")

        for i, page in enumerate(pages_to_process):
            page_width = page.mediabox.width
            page_height = page.mediabox.height

            x_scale = target_width / page_width
            y_scale = target_height / page_height
            scale = min(x_scale, y_scale)

            dest_page = writer.add_blank_page(width=target_width,
                                              height=target_height)

            dest_page.merge_transformed_page(
                page,
                Transformation().scale(scale)
            )
            # Print a message every 10 pages processed.
            if num_pages > chunk_size and (i + 1) % chunk_size == 0 or i == num_pages - 1:
                print(f"Processed {i + 1} of {num_pages} pages.")

        print("\nFinalizing PDF file...")
        with open(self.output_pdf_path, "wb") as output_file:
            writer.write(output_file)
        print("Finalization complete.")

        print(f"Success: The resized PDF was saved to "
              f"'{self.output_pdf_path}'.")

    def modify_pdf(self):
        """
        A unified function to modify a PDF file based on the parameters
        provided during initialization.
        """
        actions = {
            'duplicate': self._duplicate_pages,
            'add_notes': self._add_note_margin,
            'merge_side_by_side': self._merge_pdf_side_by_side,
            'resize': self._resize_pdf,
        }

        if self.action not in actions:
            print(f"Error: Invalid action '{self.action}'. Supported actions are:"
                  f" {', '.join(actions.keys())}")
            return

        reader = None
        writer = None
        try:
            if self.input_pdf_path:
                self._verify_paths(self.input_pdf_path)
                self._print_pdf_info(self.input_pdf_path,
                                     "Before Modification")
                reader = PdfReader(self.input_pdf_path)
            else:
                print("Warning: No input PDF provided. This is only expected"
                      " for some actions.")

            writer = PdfWriter()
            if self.append_to_existing and os.path.exists(self.output_pdf_path):
                print(f"Appending pages to existing file: "
                      f"'{self.output_pdf_path}'")
                try:
                    existing_reader = PdfReader(self.output_pdf_path)
                    for page in existing_reader.pages:
                        writer.add_page(page)
                    existing_reader.close()
                except Exception as e:
                    print(f"Warning: Could not read existing PDF for "
                          f"appending. Creating a new file instead. "
                          f"Error: {e}")

            total_pages = len(reader.pages)

            if self.input_start_page < 0:
                raise ValueError("Error: 'input_start_page' cannot be negative.")
            if self.input_end_page is not None and self.input_end_page <= self.input_start_page:
                raise ValueError("Error: 'input_end_page' must be greater than 'input_start_page'.")
            if self.input_start_page >= total_pages:
                raise ValueError(f"Error: 'input_start_page' is out of bounds. "
                                 f"Document has {total_pages} pages.")

            end_page = self.input_end_page if self.input_end_page is not None else total_pages
            if end_page > total_pages:
                end_page = total_pages
                print(f"Warning: 'input_end_page' was greater than the total "
                      f"number of pages. Processing up to the last page "
                      f"({total_pages}).")

            pages_to_process = reader.pages[self.input_start_page:end_page]

            if not pages_to_process:
                print("Error: The specified page range is empty. "
                      "No action was performed.")
                return

            # Pass the list of pages and the writer to the selected action function
            actions[self.action](pages_to_process=pages_to_process, writer=writer)

        except FileNotFoundError as e:
            print(f"Error: File not found. Details: {e}")
        except ValueError as e:
            print(f"Error: Invalid argument for action '{self.action}'. "
                  f"Details: {e}")
        except TypeError as e:
            print(f"Error: Missing or incorrect arguments for action "
                  f"'{self.action}'. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during action "
                  f"'{self.action}': {e}")
        finally:
            if reader:
                reader.close()
            if writer:
                writer.close()


# --- Example Usage ---
if __name__ == "__main__":

    # Example 1: Duplicate each page of the PDF with a default output path
    print("--- Running Example 1: Duplicating pages with default "
          "output path ---")
    # Notice we now pass the action and all other parameters in the init method.
    pdf_modifier_1 = PDFModifier(input_pdf_path="pdf-files/sample.pdf",
                                 action='duplicate')
    print(f"Default output path is: {pdf_modifier_1.output_pdf_path}")
    pdf_modifier_1.modify_pdf()
    pdf_modifier_1._print_pdf_info(pdf_modifier_1.output_pdf_path,
                                   "After Modification")
    print("\n")

    # Example 2: Demonstrate merging pages side-by-side with an
    # explicit output path
    print("--- Running Example 2: Merging pages side-by-side ---")
    pdf_modifier_2 = PDFModifier(input_pdf_path="pdf-files/sample.pdf",
                                 output_pdf_path="pdf-files/sample_merged.pdf",
                                 action='merge_side_by_side',
                                 merge_pdf_path="pdf-files/merge_page.pdf")
    pdf_modifier_2.modify_pdf()
    pdf_modifier_2._print_pdf_info("pdf-files/sample_merged.pdf",
                                   "After Modification")
    print("\n")

    # Example 3: Demonstrate adding a thick margin for notes
    print("--- Running Example 3: Adding a thick margin for notes "
          "(default 50% margin) ---")
    pdf_modifier_3 = PDFModifier(input_pdf_path="pdf-files/sample.pdf",
                                 output_pdf_path="pdf-files/"
                                 "sample_notes_default.pdf",
                                 action='add_notes',
                                 background_pdf_path="pdf-files/grid_paper.pdf",
                                 margin_proportion=0.5)
    pdf_modifier_3.modify_pdf()
    pdf_modifier_3._print_pdf_info("pdf-files/sample_notes_default.pdf",
                                   "After Modification")
    print("\n")

    # Example 4: Demonstrate adding a thick margin for notes
    # (custom 30% margin)
    print("--- Running Example 4: Adding a thick margin for notes "
          "(custom 30% margin) ---")
    pdf_modifier_4 = PDFModifier(input_pdf_path="pdf-files/sample.pdf",
                                 output_pdf_path="pdf-files/"
                                 "sample_notes_custom.pdf",
                                 action='add_notes',
                                 background_pdf_path="pdf-files/grid_paper.pdf",
                                 margin_proportion=0.3)
    pdf_modifier_4.modify_pdf()
    pdf_modifier_4._print_pdf_info("pdf-files/sample_notes_custom.pdf",
                                   "After Modification")
    print("\n")

    # Example 5: Demonstrate resizing a PDF to a specific size
    print("--- Running Example 5: Resizing PDF to Letter size ---")
    pdf_modifier_5 = PDFModifier(input_pdf_path="pdf-files/sample.pdf",
                                 output_pdf_path="pdf-files/"
                                 "sample_resized.pdf",
                                 action='resize', target_size="Letter")
    pdf_modifier_5.modify_pdf()
    pdf_modifier_5._print_pdf_info("pdf-files/sample_resized.pdf",
                                   "After Modification")
    print("\n")

    # Example 6: Demonstrate error handling for a non-existent file
    print("--- Running Example 6: Demonstrating file not found error ---")
    try:
        pdf_modifier_6 = PDFModifier(input_pdf_path="pdf-files/"
                                                    "non_existent.pdf",
                                     output_pdf_path="pdf-files/"
                                     "non_existent_output.pdf",
                                     action='duplicate')
        pdf_modifier_6.modify_pdf()
    except Exception as e:
        print(e)
    pdf_modifier_6._print_pdf_info("pdf-files/non_existent_output.pdf",
                                   "After Modification")
    print("\n")

    # Example 7: Demonstrate error handling for a missing argument
    print("--- Running Example 7: Demonstrating missing argument error ---")
    pdf_modifier_7 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_merged_error.pdf",
        action='merge_side_by_side'
        # merge_pdf_path is intentionally missing here
    )
    pdf_modifier_7.modify_pdf()
    pdf_modifier_7._print_pdf_info("pdf-files/sample_merged_error.pdf",
                                   "After Modification")
    print("\n")

    # Example 8: Demonstrate using the new page range functionality
    print("--- Running Example 8: Duplicating a specific page range (pages 1 to 3) ---")
    pdf_modifier_8 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_range_duplicate.pdf",
        action='duplicate',
        input_start_page=1,
        input_end_page=3
    )
    # This will process pages from index 1 (the second page) up to but not including index 3
    pdf_modifier_8.modify_pdf()
    pdf_modifier_8._print_pdf_info("pdf-files/sample_range_duplicate.pdf",
                                   "After Modification")
    print("\n")
