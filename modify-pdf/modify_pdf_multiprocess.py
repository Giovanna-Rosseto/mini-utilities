import os
import multiprocessing
import tempfile
import shutil
import io
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from copy import deepcopy

# Dictionary of standard paper sizes in PostScript points (1/72 of an inch)
# This is kept as a global constant as it is a static lookup table.
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
    A class to handle various PDF modification tasks using multiprocessing.
    It encapsulates the logic for different actions like duplicating,
    resizing, and merging PDFs.
    """

    def __init__(self, input_pdf_path=None, output_pdf_path=None, action=None,
                 background_pdf_path=None, margin_proportion=0.5,
                 merge_pdf_path=None, target_size="A4",
                 input_start_page=0, input_end_page=None, num_processes=None):
        """
        Initializes the PDFModifier class with all necessary parameters for
        a specific modification task.

        Args:
            input_pdf_path (str, optional): The path to the input PDF file.
            output_pdf_path (str, optional): The path to save the output PDF
                                             file.
            action (str or list): The name(s) of the modification function(s)
                                  to call. Supported actions: 'duplicate',
                                  'add_notes', 'merge_side_by_side', 'resize'.
            background_pdf_path (str, optional): The path to a background PDF
                                                 for 'add_notes'.
            margin_proportion (float, optional): The proportion of the page
                                                 for the margin in 'add_notes'.
            merge_pdf_path (str, optional): The path to the PDF to merge
                                            for 'merge_side_by-side'.
            target_size (str, optional): The target paper size for 'resize'.
            input_start_page (int, optional): The starting page index
                                             (0-based) for processing.
                                             Defaults to 0.
            input_end_page (int, optional): The ending page index (0-based,
                                             exclusive) for processing.
                                             Defaults to the end of the
                                             document.
            num_processes (int, optional): The number of processes to use.
                                             If not specified, defaults to the
                                             number of available CPU cores.
        """
        self.input_pdf_path = input_pdf_path

        # If no output path is provided, generate a default one
        if output_pdf_path:
            self.output_pdf_path = output_pdf_path
        elif self.input_pdf_path:
            base, ext = os.path.splitext(self.input_pdf_path)
            self.output_pdf_path = f"{base}_output{ext}"
        else:
            raise ValueError("'input_pdf_path' or 'output_pdf_path' must be "
                             "provided during initialization.")

        # Store all parameters as instance attributes
        # Ensure action is always a list for chained processing
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
        self.num_processes = num_processes

    @staticmethod
    def _verify_paths(*paths):
        """
        Internal helper function to check if all provided file paths exist.
        """
        for path in paths:
            if path and not os.path.exists(path):
                raise FileNotFoundError(
                    f"Error: The file '{path}' was not found.")
        return True

    @staticmethod
    def _print_pdf_info(pdf_path, title):
        """
        Internal helper function to print quality metadata for a given PDF.
        This includes page count and the dimensions of the first page.
        """
        if not pdf_path or not os.path.exists(pdf_path):
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
                print(f"     - Page count: {num_pages}")
                print(f"     - First page dimensions: {width:.2f}pt x "
                      f"{height:.2f}pt")
            else:
                print(f"{title} - File: '{pdf_path}' has no pages.")
        except Exception as e:
            print(f"Error reading PDF info for '{pdf_path}': {e}")
        finally:
            if reader:
                reader.close()

    @staticmethod
    def _process_chunk(args_dict):
        """
        A static method to process a chunk of pages and save them to a
        temporary file. This function is designed to be run in a separate
        process. It accepts all arguments in a single dictionary.
        """
        try:
            # Unpack arguments from the dictionary
            input_pdf_path = args_dict['input_pdf_path']
            temp_output_path = args_dict['temp_output_path']
            actions = args_dict['actions']
            start_page = args_dict['start_page']
            end_page = args_dict['end_page']

            reader = PdfReader(input_pdf_path)

            # Use an initial writer to hold the original pages for the chunk
            current_writer = PdfWriter()
            for page in reader.pages[start_page:end_page]:
                current_writer.add_page(page)

            pages_to_process = list(current_writer.pages)

            if not pages_to_process:
                print(f"Warning: No pages to process in chunk "
                      f"{start_page}-{end_page}.")
                return temp_output_path

            # Process each action in the list sequentially
            for action in actions:
                # The input for the next action is the output of current one.
                # Use an in-memory buffer to pass the PDF data.
                buffer = io.BytesIO()
                current_writer.write(buffer)
                buffer.seek(0)

                temp_reader = PdfReader(buffer)
                pages_to_process_for_action = list(temp_reader.pages)
                current_writer = PdfWriter()  # Reset writer for next action

                if action == 'duplicate':
                    for page in pages_to_process_for_action:
                        current_writer.add_page(page)
                        current_writer.add_page(page)

                elif action == 'add_notes':
                    background_pdf_path = args_dict.get('background_pdf_path')
                    margin_proportion = args_dict.get('margin_proportion', 0.5)

                    background_reader = None
                    try:
                        if background_pdf_path:
                            background_reader = PdfReader(background_pdf_path)
                            if not background_reader.pages:
                                raise ValueError(
                                    "Background file has no pages.")

                        for page in pages_to_process_for_action:
                            page_width = page.mediabox.width
                            page_height = page.mediabox.height
                            ideal_width = page_width / (1 - margin_proportion)
                            ideal_height = page_height

                            dest_page = current_writer.add_blank_page(
                                width=ideal_width, height=ideal_height)
                            dest_page.merge_page(page)

                            if background_reader:
                                background_page = background_reader.pages[0]
                                background_page_height = \
                                    background_page.mediabox.height
                                scale_bg = ideal_height /\
                                    background_page_height
                                dest_page.merge_transformed_page(
                                    background_page,
                                    Transformation().scale(
                                        scale_bg).translate(page_width, 0)
                                )
                    finally:
                        if background_reader:
                            background_reader.close()

                elif action == 'merge_side_by_side':
                    merge_pdf_path = args_dict.get('merge_pdf_path')
                    merge_reader = None
                    try:
                        merge_reader = PdfReader(merge_pdf_path)
                        if not merge_reader.pages:
                            raise ValueError(
                                "Merge PDF must contain at least one page.")
                        original_merge_page = merge_reader.pages[0]
                        width, height = PaperSize.A4.height, PaperSize.A4.width
                        for page in pages_to_process_for_action:
                            dest_page = current_writer.add_blank_page(
                                width=width, height=height)
                            merge_page = deepcopy(original_merge_page)
                            page_width, page_height = (
                                page.mediabox.width, page.mediabox.height)
                            scale = min((width / 2) / page_width,
                                        height / page_height)
                            scale_merge = min(
                                (width / 2) / merge_page.mediabox.width,
                                height / merge_page.mediabox.height)
                            dest_page.merge_transformed_page(
                                page, Transformation().scale(scale))
                            dest_page.merge_transformed_page(
                                merge_page, Transformation().scale(
                                    scale_merge).translate(width / 2, 0)
                            )
                    finally:
                        if merge_reader:
                            merge_reader.close()

                elif action == 'resize':
                    target_size = args_dict.get('target_size', 'A4')
                    target_dimensions = PAPER_SIZES.get(target_size)
                    if not target_dimensions:
                        raise ValueError(f"Invalid size '{target_size}'.")
                    target_width, target_height = target_dimensions

                    for page in pages_to_process_for_action:
                        page_width, page_height = (
                            page.mediabox.width, page.mediabox.height)
                        scale = min(target_width / page_width,
                                    target_height / page_height)
                        dest_page = current_writer.add_blank_page(
                            width=target_width, height=target_height)
                        dest_page.merge_transformed_page(
                            page, Transformation().scale(scale))

            # The final output of the chained actions is written to tempfile
            with open(temp_output_path, "wb") as output_file:
                current_writer.write(output_file)

            reader.close()
            print(f"Chunk processed and saved to {temp_output_path}")
            return temp_output_path

        except Exception as e:
            print(f"Error in process chunk {start_page}-{end_page}: {e}")
            return None

    def modify_pdf(self):
        """
        A unified function to modify a PDF file using a multiprocessing Pool.
        """
        actions = ['duplicate', 'add_notes', 'merge_side_by_side', 'resize']
        for action in self.actions:
            if action not in actions:
                print(f"Error: Invalid action '{action}'. Supported actions "
                      f"are: {', '.join(actions)}")
                return

        reader = None
        temp_dir = None
        try:
            # First, check if all required input files exist.
            self._verify_paths(self.input_pdf_path)
            # Depending on the action, other files might be required.
            if 'add_notes' in self.actions:
                self._verify_paths(self.background_pdf_path)
            if 'merge_side_by_side' in self.actions:
                self._verify_paths(self.merge_pdf_path)

            self._print_pdf_info(self.input_pdf_path, "Before Modification")

            reader = PdfReader(self.input_pdf_path)
            total_pages = len(reader.pages)

            if self.input_start_page < 0:
                raise ValueError(
                    "Error: 'input_start_page' cannot be negative.")
            if (self.input_end_page is not None and
                    self.input_end_page <= self.input_start_page):
                raise ValueError(
                    "Error: 'input_end_page' must be greater than "
                    "'input_start_page'.")
            if self.input_start_page >= total_pages:
                raise ValueError(
                    f"Error: 'input_start_page' is out of bounds. Document has"
                    f" {total_pages} pages.")

            end_page = (self.input_end_page if self.input_end_page is not None
                        else total_pages)
            end_page = min(end_page, total_pages)

            if end_page <= self.input_start_page:
                print("Error: The specified page range is empty. "
                      "No action was performed.")
                return

            # Determine the number of processes to use.
            num_processes = (self.num_processes if self.num_processes is not
                             None else multiprocessing.cpu_count())
            if num_processes <= 0:
                num_processes = 1
                print("Warning: Number of processes must be positive. "
                      "Defaulting to 1.")

            chunk_size = max(1, (end_page - self.input_start_page) //
                             num_processes)

            pool = multiprocessing.Pool(processes=num_processes)
            temp_dir = tempfile.mkdtemp()

            tasks = []

            # Create a list of dictionaries for each process
            for i in range(self.input_start_page, end_page, chunk_size):
                chunk_start = i
                chunk_end = min(i + chunk_size, end_page)

                temp_file = os.path.join(temp_dir,
                                         f"temp_{chunk_start}_{chunk_end}.pdf")

                # Pass all relevant parameters in a single dictionary
                tasks.append({
                    'input_pdf_path': self.input_pdf_path,
                    'temp_output_path': temp_file,
                    'actions': self.actions,
                    'start_page': chunk_start,
                    'end_page': chunk_end,
                    'background_pdf_path': self.background_pdf_path,
                    'margin_proportion': self.margin_proportion,
                    'merge_pdf_path': self.merge_pdf_path,
                    'target_size': self.target_size,
                })

            print(f"Starting multiprocessing with {num_processes} processes "
                  f"for {len(tasks)} chunks.")
            results = pool.map(self._process_chunk, tasks)
            pool.close()
            pool.join()

            # Merge the temporary files
            final_writer = PdfWriter()
            for temp_path in results:
                if temp_path and os.path.exists(temp_path):
                    temp_reader = PdfReader(temp_path)
                    for page in temp_reader.pages:
                        final_writer.add_page(page)

            # Write final output
            print("\nFinalizing PDF file...")
            with open(self.output_pdf_path, "wb") as f:
                final_writer.write(f)

            print(f"Success: The modified PDF was saved to "
                  f"'{self.output_pdf_path}'.")
            self._print_pdf_info(self.output_pdf_path, "After Modification")

        except FileNotFoundError as e:
            print(f"Error: File not found. Details: {e}")
        except ValueError as e:
            print(f"Error: Invalid argument. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during modification: {e}")
        finally:
            if reader:
                reader.close()
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                    print("Cleaned up temporary files.")
                except OSError as e:
                    print(f"Error during temporary directory cleanup: {e}")


# --- Example Usage ---
if __name__ == "__main__":

    # Get the absolute path of the directory where the script is located
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Path to your PDF files. The script now expects these files to exist.
    PDF_FILES_DIR = os.path.join(BASE_DIR, "test", "pdf-files")

    # Define file paths using os.path.join for platform independence
    SAMPLE_PDF_PATH = os.path.join(PDF_FILES_DIR, "sample.pdf")
    SAMPLE2_PDF_PATH = os.path.join(PDF_FILES_DIR, "sample2.pdf")
    GRID_PAPER_PDF_PATH = os.path.join(PDF_FILES_DIR, "grid_paper.pdf")
    MERGE_PAGE_PDF_PATH = os.path.join(PDF_FILES_DIR, "merge_page.pdf")

    # Check for all required files before running examples
    print("Checking for required PDF files...")
    required_files = [SAMPLE_PDF_PATH, SAMPLE2_PDF_PATH,
                      GRID_PAPER_PDF_PATH, MERGE_PAGE_PDF_PATH]
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"Error: The required file '{file_path}' was not found. "
                  f"Please place your sample files in the directory.")
            exit()
    print("PDF file check complete.")
    print("\n")

    # Example 1: Duplicate each page of the PDF with a default output path
    print("--- Running Example 1: Duplicating pages with default "
          "output path ---")
    pdf_modifier_1 = PDFModifier(input_pdf_path=SAMPLE_PDF_PATH,
                                 action='duplicate')
    print(f"Default output path is: {pdf_modifier_1.output_pdf_path}")
    pdf_modifier_1.modify_pdf()
    print("\n")

    # Example 2: Demonstrate merging pages side-by-side with an
    # explicit output path, using merge_page.pdf as the second document
    print("--- Running Example 2: Merging pages side-by-side (using "
          "merge_page.pdf) ---")
    pdf_modifier_2 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(PDF_FILES_DIR, "sample_merged.pdf"),
        action='merge_side_by_side',
        merge_pdf_path=MERGE_PAGE_PDF_PATH)
    pdf_modifier_2.modify_pdf()
    print("\n")

    # Example 3: Demonstrate adding a thick margin for notes
    print("--- Running Example 3: Adding a thick margin for notes "
          "(default 50% margin) ---")
    pdf_modifier_3 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(PDF_FILES_DIR,
                                     "sample_notes_default.pdf"),
        action='add_notes',
        background_pdf_path=GRID_PAPER_PDF_PATH,
        margin_proportion=0.5)
    pdf_modifier_3.modify_pdf()
    print("\n")

    # Example 4: Demonstrate adding a thick margin for notes
    # (custom 30% margin)
    print("--- Running Example 4: Adding a thick margin for notes "
          "(custom 30% margin) ---")
    pdf_modifier_4 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(PDF_FILES_DIR, "sample_notes_custom.pdf"),
        action='add_notes',
        background_pdf_path=GRID_PAPER_PDF_PATH,
        margin_proportion=0.3)
    pdf_modifier_4.modify_pdf()
    print("\n")

    # Example 5: Demonstrate resizing a PDF to a specific size
    print("--- Running Example 5: Resizing PDF to Letter size ---")
    pdf_modifier_5 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(PDF_FILES_DIR, "sample_resized.pdf"),
        action='resize', target_size="Letter")
    pdf_modifier_5.modify_pdf()
    print("\n")

    # Example 6: Demonstrate using the new page range functionality
    print("--- Running Example 6: Duplicating a specific page range "
          "(pages 1 to 3) ---")
    pdf_modifier_6 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(
            PDF_FILES_DIR, "sample_range_duplicate.pdf"),
        action='duplicate',
        input_start_page=1,
        input_end_page=3
    )
    pdf_modifier_6.modify_pdf()
    print("\n")

    # Example 7: Demonstrate merging sample.pdf and sample2.pdf side-by-side
    print("--- Running Example 7: Merging sample.pdf and sample2.pdf "
          "side-by-side ---")
    pdf_modifier_7 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(
            PDF_FILES_DIR, "sample_sample2_merged.pdf"),
        action='merge_side_by_side',
        merge_pdf_path=SAMPLE2_PDF_PATH
    )
    pdf_modifier_7.modify_pdf()
    print("\n")

    # Example 8: Demonstrate chaining actions: duplicate, then resize
    print("--- Running Example 8: Chaining actions ('duplicate', 'resize')---")
    pdf_modifier_8 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(
            PDF_FILES_DIR, "sample_duplicate_and_resized.pdf"),
        action=['duplicate', 'resize'],
        target_size="A5"
    )
    pdf_modifier_8.modify_pdf()
    print("\n")

    # NEW Example 9: Demonstrate limiting the number of processes to 2
    print("---Running NEW Example 9: Limiting processes to 2 ('duplicate')---")
    pdf_modifier_9 = PDFModifier(
        input_pdf_path=SAMPLE_PDF_PATH,
        output_pdf_path=os.path.join(
            PDF_FILES_DIR, "sample_duplicate_limited_processes.pdf"),
        action='duplicate',
        num_processes=2
    )
    pdf_modifier_9.modify_pdf()
    print("\n")
