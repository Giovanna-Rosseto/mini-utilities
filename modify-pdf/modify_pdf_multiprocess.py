import os
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from copy import deepcopy
from multiprocessing import Process, Queue
from queue import Empty
import time
from io import BytesIO

# Dictionary of standard paper sizes in PostScript points
# (1/72 of an inch)
# This is kept as a global constant as it is a static lookup table.
# We will dynamically add landscape versions of each size.
_BASE_PAPER_SIZES = {
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

# Create a final PAPER_SIZES dictionary including landscape variations
PAPER_SIZES = deepcopy(_BASE_PAPER_SIZES)
for name, (width, height) in _BASE_PAPER_SIZES.items():
    PAPER_SIZES[f"{name}_Landscape"] = (height, width)


class PDFModifier:
    """
    A class to handle various PDF modification tasks.
    It encapsulates the logic for different actions like duplicating,
    resizing, and merging PDFs.
    """

    def __init__(self, input_pdf_path=None, output_pdf_path=None,
                 action=None, background_pdf_path=None,
                 margin_proportion=0.5, merge_pdf_path=None,
                 target_size="A4", input_start_page=0,
                 input_end_page=None, append_to_existing=False,
                 compress_output=False):
        """
        Initializes the PDFModifier class with all necessary parameters for
        a specific modification task.

        If `output_pdf_path` is not provided, a default path is generated
        by appending '_output' before the file extension of `input_pdf_path`.

        Args:
            input_pdf_path (str, optional): The path to the input PDF file.
            output_pdf_path (str, optional): The path to save the output PDF.
            action (str or list): The name(s) of the modification function
                                  to call. Can be a single string or a list.
                                  Supported actions: 'duplicate', 'add_notes',
                                  'merge_side_by_side', 'resize'.
            background_pdf_path (str, optional): The path to a background PDF
                                                  for 'add_notes'.
            margin_proportion (float, optional): The proportion of the page
                                                 for the margin in 'add_notes'.
            merge_pdf_path (str, optional): The path to the PDF to merge
                                            for 'merge_side_by_side'.
            target_size (str, optional): The target paper size for 'resize'.
                                         Now includes `_Landscape` variations.
            input_start_page (int, optional): The starting page index (0-based)
                                              for processing. Defaults to 0.
            input_end_page (int, optional): The ending page index (0-based,
                                            exclusive) for processing. Defaults
                                            to the end of the document.
            append_to_existing (bool, optional): If True, appends the new pages
                                                 to an existing output PDF.
                                                 Defaults to False (overwrite).
            compress_output (bool, optional): If True, the final output PDF
                                              will be re-saved to attempt to
                                              reduce the file size.
                                              Defaults to False.
        """
        self.input_pdf_path = input_pdf_path

        # If no output path is provided, generate a default one
        if output_pdf_path:
            self.output_pdf_path = output_pdf_path
        elif self.input_pdf_path:
            base, ext = os.path.splitext(self.input_pdf_path)
            self.output_pdf_path = f"{base}_output{ext}"
        else:
            raise ValueError(
                "'input_pdf_path' or 'output_pdf_path' "
                "must be provided during initialization.")

        # Store all parameters as instance attributes
        if isinstance(action, str):
            self.actions = [action]
        elif isinstance(action, list):
            self.actions = action
        else:
            raise TypeError("The 'action' parameter must be a string or a "
                            "list of strings.")

        self.background_pdf_path = background_pdf_path
        self.margin_proportion = margin_proportion
        self.merge_pdf_path = merge_pdf_path
        self.target_size = target_size
        self.input_start_page = input_start_page
        self.input_end_page = input_end_page
        self.append_to_existing = append_to_existing
        self.compress_output = compress_output

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

    def _duplicate_pages(self, pages_to_process):
        """
        Duplicates each page in a list of PDF pages.
        Returns a new list with the duplicated pages.
        """
        new_pages = []
        num_pages = len(pages_to_process)
        if num_pages == 0:
            return new_pages

        chunk_size = 10
        print(f"Starting 'duplicate' action on {num_pages} pages...")

        for i, page in enumerate(pages_to_process):
            new_pages.append(page)
            new_pages.append(page)
            if num_pages > chunk_size and (i + 1) % chunk_size == 0 or \
                    i == num_pages - 1:
                print(f"Processed {i + 1} of {num_pages} pages for "
                      f"'duplicate'.")

        return new_pages

    def _add_note_margin(self, pages_to_process):
        """
        Adds a note-taking margin to each page by placing the original page
        on a new page with a user-defined margin proportion.
        Returns a new list of pages with the added margin.
        """
        new_pages = []
        if not 0 <= self.margin_proportion < 1:
            raise ValueError("Error: 'margin_proportion' must be between "
                             "0 and 1.")

        num_pages = len(pages_to_process)
        if num_pages == 0:
            return new_pages

        chunk_size = 10
        print(f"Starting 'add_notes' action on {num_pages} pages...")

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

                temp_writer = PdfWriter()
                dest_page = temp_writer.add_blank_page(
                    width=ideal_width, height=ideal_height)
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
                new_pages.append(dest_page)

                if num_pages > chunk_size and (i + 1) % chunk_size == 0 or \
                        i == num_pages - 1:
                    print(f"Processed {i + 1} of {num_pages} pages for "
                          f"'add_notes'.")
        finally:
            if background_reader:
                background_reader.close()

        return new_pages

    def _merge_pdf_side_by_side(self, pages_to_process):
        """
        Merges each page of a PDF with a page from another PDF, placing them
        side-by-side on a new A4 landscape page.
        Returns a new list of pages.
        """
        new_pages = []
        num_pages = len(pages_to_process)
        if num_pages == 0:
            return new_pages

        chunk_size = 10
        print("Starting 'merge_side_by_side' action on "
              f"{num_pages} pages...")

        merge_reader = None
        try:
            self._verify_paths(self.merge_pdf_path)
            merge_reader = PdfReader(self.merge_pdf_path)
            if len(merge_reader.pages) < 1:
                raise ValueError("Error: The merge PDF must contain at least "
                                 "one page.")

            original_merge_page = merge_reader.pages[0]

            width = PAPER_SIZES["A4_Landscape"][0]
            height = PAPER_SIZES["A4_Landscape"][1]

            for i, page in enumerate(pages_to_process):
                temp_writer = PdfWriter()
                dest_page = temp_writer.add_blank_page(width=width,
                                                       height=height)
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
                new_pages.append(dest_page)

                if num_pages > chunk_size and (i + 1) % chunk_size == 0 or \
                        i == num_pages - 1:
                    print(f"Processed {i + 1} of {num_pages} pages for "
                          f"'merge_side_by_side'.")
        finally:
            if merge_reader:
                merge_reader.close()

        return new_pages

    def _resize_pdf(self, pages_to_process):
        """
        Resizes each page of a PDF to a specific paper size,
        scaling the content to fit within the new dimensions.
        Returns a new list of pages.
        """
        new_pages = []
        target_dimensions = PAPER_SIZES.get(self.target_size)
        if not target_dimensions:
            raise ValueError(
                f"Error: Invalid target size '{self.target_size}'.\n"
                "Supported sizes are: "
                f"{', '.join(PAPER_SIZES.keys())}")

        num_pages = len(pages_to_process)
        if num_pages == 0:
            return new_pages

        chunk_size = 10
        target_width, target_height = target_dimensions
        print(f"Starting 'resize' action on {num_pages} pages...")

        for i, page in enumerate(pages_to_process):
            page_width = page.mediabox.width
            page_height = page.mediabox.height

            x_scale = target_width / page_width
            y_scale = target_height / page_height
            scale = min(x_scale, y_scale)

            temp_writer = PdfWriter()
            dest_page = temp_writer.add_blank_page(width=target_width,
                                                   height=target_height)

            dest_page.merge_transformed_page(
                page,
                Transformation().scale(scale)
            )
            new_pages.append(dest_page)

            if num_pages > chunk_size and (i + 1) % chunk_size == 0 or \
                    i == num_pages - 1:
                print(f"Processed {i + 1} of {num_pages} pages for "
                      f"'resize'.")

        return new_pages

    def _modify_and_save(self, q=None):
        """
        The core logic for modifying and saving the PDF. This method can be
        called directly or run in a separate process. It handles all
        modifications, progress updates, and error handling.
        """
        actions = {
            'duplicate': self._duplicate_pages,
            'add_notes': self._add_note_margin,
            'merge_side_by_side': self._merge_pdf_side_by_side,
            'resize': self._resize_pdf,
        }

        # Validate that all requested actions are supported
        for action in self.actions:
            if action not in actions:
                error_msg = (f"Error: Invalid action '{action}'. "
                             "Supported actions are: "
                             f"{', '.join(actions.keys())}")
                if q:
                    q.put(error_msg)
                print(error_msg)
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

            pages_to_process = []
            if reader:
                total_pages = len(reader.pages)
                if self.input_start_page < 0:
                    raise ValueError("Error: 'input_start_page' cannot be "
                                     "negative.")
                if self.input_end_page is not None and \
                        self.input_end_page <= self.input_start_page:
                    raise ValueError("Error: 'input_end_page' must be greater"
                                     " than 'input_start_page'.")
                if self.input_start_page >= total_pages:
                    raise ValueError("Error: 'input_start_page' is out of "
                                     f"bounds. Document has {total_pages} "
                                     "pages.")

                end_page = self.input_end_page if \
                    self.input_end_page is not None else total_pages
                if end_page > total_pages:
                    end_page = total_pages
                    print("Warning: 'input_end_page' was greater than the "
                          f"total number of pages. Processing up to the "
                          f"last page ({total_pages}).")

                pages_to_process = list(reader.pages[self.input_start_page:
                                                     end_page])

            if not pages_to_process and self.actions:
                print("Error: The specified page range is empty. "
                      "No actions were performed.")
                return

            # Execute actions in a chain
            for action in self.actions:
                pages_to_process = actions[action](
                    pages_to_process=pages_to_process)

            # Final write to the output file
            writer = PdfWriter()
            if (self.append_to_existing and
                    os.path.exists(self.output_pdf_path)):
                print(f"\nAppending pages to existing file: "
                      f"'{self.output_pdf_path}'")
                try:
                    existing_reader = PdfReader(self.output_pdf_path)
                    for page in existing_reader.pages:
                        writer.add_page(page)
                    existing_reader.close()
                except Exception as e:
                    print("Warning: Could not read existing PDF for "
                          f"appending. Creating a new file instead. "
                          f"Error: {e}")

            for page in pages_to_process:
                writer.add_page(page)

            print("\nFinalizing PDF file...")

            if self.compress_output:
                print("Compressing output PDF...")
                temp_output = BytesIO()
                writer.write(temp_output)
                temp_output.seek(0)
                compressed_reader = PdfReader(temp_output)
                compressed_writer = PdfWriter()
                for page in compressed_reader.pages:
                    compressed_writer.add_page(page)

                with open(self.output_pdf_path, "wb") as output_file:
                    compressed_writer.write(output_file)
                print("Compression complete.")

            else:
                with open(self.output_pdf_path, "wb") as output_file:
                    writer.write(output_file)
            
            print("Finalization complete.")
            print(f"Success: The modified PDF was saved to "
                  f"'{self.output_pdf_path}'.")

            if q:
                q.put("success")

        except FileNotFoundError as e:
            if q:
                q.put(f"Error: File not found. Details: {e}")
            print(f"Error: File not found. Details: {e}")
        except ValueError as e:
            if q:
                q.put("Error: Invalid argument for action. "
                      f"Details: {e}")
            print("Error: Invalid argument for action. "
                  f"Details: {e}")
        except TypeError as e:
            if q:
                q.put("Error: Missing or incorrect arguments. "
                      f"Details: {e}")
            print("Error: Missing or incorrect arguments. "
                  f"Details: {e}")
        except Exception as e:
            if q:
                q.put(f"An unexpected error occurred: {e}")
            print(f"An unexpected error occurred: {e}")
        finally:
            if reader:
                reader.close()
            if writer:
                writer.close()

    def run_in_separate_process(self):
        """
        Spawns a new process to run the PDF modification, allowing the
        main program to remain responsive.
        """
        # A Queue is used for communication between the main process
        # and the worker process
        q = Queue()
        process = Process(target=self._modify_and_save, args=(q,))
        process.start()

        print(f"Modification process started with PID: {process.pid}")
        print("Please wait for the process to complete...")

        # Wait for a result from the queue
        while process.is_alive():
            time.sleep(1)

        # Check the queue for the result after the process has finished
        try:
            result = q.get_nowait()
            if result == "success":
                print(f"\nModification process with PID {process.pid} "
                      "completed successfully.")
            else:
                print(f"\nModification process with PID {process.pid} "
                      f"failed with error: {result}")
        except Empty:
            # This can happen if the process finished without putting
            # anything in the queue.
            print("Modification process with PID "
                  f"{process.pid} finished, but no result was returned.")
        except Exception as e:
            print("An error occurred while getting the result from the "
                  f"queue: {e}")

    def modify_pdf(self):
        """
        A unified function to modify a PDF file based on the parameters
        provided during initialization.
        """
        self._modify_and_save()


def usage_examples():
    # --- Example Usage ---

    # Example 1: Duplicate each page of the PDF and then resize it
    # in a separate process
    print("--- Running Example 1: Chaining actions ('duplicate', "
          "'resize') ---")
    pdf_modifier_1 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_duplicate_and_resized.pdf",
        action=['duplicate', 'resize'],
        target_size="A5"
    )
    pdf_modifier_1.run_in_separate_process()
    print("\nMain program is not frozen and can continue to run...")
    time.sleep(5)
    pdf_modifier_1._print_pdf_info(
        "pdf-files/sample_duplicate_and_resized.pdf",
        "After Chained Modification"
    )
    print("\n")

    # Example 2: Add notes margin and then resize in a separate process
    print("--- Running Example 2: Chaining actions ('add_notes', "
          "'resize') ---")
    pdf_modifier_2 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_notes_and_resized.pdf",
        action=['add_notes', 'resize'],
        background_pdf_path="pdf-files/grid_paper.pdf",
        margin_proportion=0.3,
        target_size="Letter"
    )
    pdf_modifier_2.run_in_separate_process()
    print("\nMain program is not frozen and can continue to run...")
    time.sleep(5)
    pdf_modifier_2._print_pdf_info(
        "pdf-files/sample_notes_and_resized.pdf",
        "After Chained Modification"
    )
    print("\n")

    # Example 3: Resize to A5_Landscape in a separate process
    print("--- Running Example 3: Resizing to A5_Landscape ---")
    pdf_modifier_3 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_a5_landscape.pdf",
        action='resize',
        target_size="A5_Landscape"
    )
    pdf_modifier_3.run_in_separate_process()
    print("\nMain program is not frozen and can continue to run...")
    time.sleep(5)
    pdf_modifier_3._print_pdf_info("pdf-files/sample_a5_landscape.pdf",
                                   "After Resize to Landscape")
    print("\n")

    # Example 4: Merge files and then apply compression
    print("--- Running Example 4: Merging and then compressing output ---")
    pdf_modifier_4 = PDFModifier(
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_merged_and_compressed.pdf",
        action='merge_side_by_side',
        merge_pdf_path="pdf-files/sample2.pdf",
        compress_output=True
    )
    pdf_modifier_4.run_in_separate_process()
    print("\nMain program is not frozen and can continue to run...")
    time.sleep(5)
    pdf_modifier_4._print_pdf_info(
        "pdf-files/sample_merged_and_compressed.pdf",
        "After Merge and Compression"
    )
    print("\n")


if __name__ == "__main__":
    usage_examples()

    # typical example
    """ OUTPUT = "path\\to\\output.pdf"
    CORNELL = "path\\to\\cornell.pdf" # my favorite notebook style
    GRID_PAPER = "path\\to\\grid_paper.pdf"
    INPUT = "path\\to\\input.pdf"
    try:
        # Create an instance of the class
        pdf_modifier = PDFModifier(
            input_pdf_path=INPUT,
            background_pdf_path=GRID_PAPER,
            merge_pdf_path=CORNELL,
            output_pdf_path=OUTPUT,
            input_start_page=11,
            input_end_page=150,
            action='add_notes', #'duplicate', 'add_notes','merge_side_by_side','resize'
            margin_proportion=0.5,
            target_size="A4_Landscape",
            compress_output=True
        )

        pdf_modifier.run_in_separate_process()
        pdf_modifier._print_pdf_info(OUTPUT, "After Process")
    except Exception as e:
        print(f"An error occurred: {e}") """
