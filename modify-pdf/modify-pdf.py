
import os
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from copy import deepcopy

# Dictionary of standard paper sizes in PostScript points (1/72 of an inch)
# Includes A, B, C, and Letter sizes for convenience.
PAPER_SIZES = {
    "A0": PaperSize.A0,
    "A1": PaperSize.A1,
    "A2": PaperSize.A2,
    "A3": PaperSize.A3,
    "A4": PaperSize.A4,
    "A5": PaperSize.A5,
    "A6": PaperSize.A6,
    "Letter": (612, 792),   # 8.5 x 11 inches
    "Legal": (612, 1008),  # 8.5 x 14 inches
    "Tabloid": (792, 1224), # 11 x 17 inches
    # B Series - based on ISO 216 dimensions
    "B0": (1000/25.4*72, 1414/25.4*72),
    "B1": (707/25.4*72, 1000/25.4*72),
    "B2": (500/25.4*72, 707/25.4*72),
    "B3": (353/25.4*72, 500/25.4*72),
    "B4": (250/25.4*72, 353/25.4*72),
    "B5": (176/25.4*72, 250/25.4*72),
    # C Series - based on ISO 216 dimensions for envelopes
    "C0": (917/25.4*72, 1297/25.4*72),
    "C1": (648/25.4*72, 917/25.4*72),
    "C2": (458/25.4*72, 648/25.4*72),
    "C3": (324/25.4*72, 458/25.4*72),
    "C4": (229/25.4*72, 324/25.4*72),
    "C5": (162/25.4*72, 229/25.4*72),
    "C6": (114/25.4*72, 162/25.4*72),
}

def _verify_paths(*paths):
    """
    Internal helper function to check if all provided file paths exist.
    """
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Error: The file '{path}' was not found.")
    return True

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
            print(f"    - First page dimensions: {width:.2f}pt x {height:.2f}pt")
        else:
            print(f"{title} - File: '{pdf_path}' has no pages.")
    except Exception as e:
        print(f"Error reading PDF info for '{pdf_path}': {e}")
    finally:
        if reader: reader.close()


def duplicate_pdf_pages(reader, writer, input_pdf_path, output_pdf_path):
    """
    Duplicates each page in a PDF file.

    Args:
        reader (PdfReader): The PdfReader object for the input file.
        writer (PdfWriter): The PdfWriter object to write to the output file.
        input_pdf_path (str): The path to the original PDF file.
        output_pdf_path (str): The path where the duplicated PDF will be saved.
    """
    for page in reader.pages:
        writer.add_page(page)
        writer.add_page(page)
    
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Success: The duplicated PDF was saved to '{output_pdf_path}'.")

def add_note_margin(reader, writer, input_pdf_path, output_pdf_path, background_pdf_path=None, margin_proportion=0.5):
    """
    Adds a note-taking margin to each page by placing the original page
    on a new page with a user-defined margin proportion.

    Args:
        reader (PdfReader): The PdfReader object for the input file.
        writer (PdfWriter): The PdfWriter object to write to the output file.
        input_pdf_path (str): The path to the original PDF file.
        output_pdf_path (str): The path where the new PDF will be saved.
        background_pdf_path (str, optional): The path to a single-page PDF to be used as a background
                                            for the notes margin. Defaults to None.
        margin_proportion (float, optional): The proportion of the page width to be used for the margin.
                                             Should be between 0 and 1. Defaults to 0.5.
    """
    if not 0 <= margin_proportion < 1:
        raise ValueError("Error: 'margin_proportion' must be between 0 and 1.")

    background_reader = None
    try:
        if background_pdf_path:
            _verify_paths(background_pdf_path)
            background_reader = PdfReader(background_pdf_path)
            if not background_reader.pages:
                raise ValueError(f"Error: The background file '{background_pdf_path}' has no pages.")
            
        for page in reader.pages:
            # Get dimensions of the original page
            page_width = page.mediabox.width
            page_height = page.mediabox.height
            
            # Calculate the ideal width for the new page to maintain the original page's size
            # while adding a margin of the specified proportion.
            ideal_width = page_width / (1 - margin_proportion)
            ideal_height = page_height

            # Create a new blank page with the calculated ideal dimensions
            dest_page = writer.add_blank_page(width=ideal_width, height=ideal_height)
            
            # --- Place the original page on the left side ---
            # No scaling is needed as the new page height matches the original.
            dest_page.merge_page(page)

            # --- Place the background page on the right side if provided ---
            if background_reader:
                background_page = background_reader.pages[0]
                background_page_width = background_page.mediabox.width
                background_page_height = background_page.mediabox.height
                
                # Scale the background page to fit the margin area, matching the new page's height.
                scale_bg = ideal_height / background_page_height
                
                # Translate the scaled background page to the right, starting after the original page.
                dest_page.merge_transformed_page(
                    background_page,
                    Transformation().scale(scale_bg).translate(page_width, 0)
                )

        with open(output_pdf_path, "wb") as output_file:
            writer.write(output_file)

        print(f"Success: The note-taking PDF was saved to '{output_pdf_path}'.")
    finally:
        if background_reader: background_reader.close()

def merge_pdf_side_by_side(reader, writer, input_pdf_path, output_pdf_path, merge_pdf_path):
    """
    Merges each page of a PDF with a page from another PDF, placing them side-by-side
    on a new A4 landscape page.

    Args:
        reader (PdfReader): The PdfReader object for the input file.
        writer (PdfWriter): The PdfWriter object to write to the output file.
        input_pdf_path (str): The path to the original PDF file.
        output_pdf_path (str): The path where the new PDF will be saved.
        merge_pdf_path (str): The path to a single-page PDF to be merged.
    """
    merge_reader = None
    try:
        merge_reader = PdfReader(merge_pdf_path)
        if len(merge_reader.pages) < 1:
            raise ValueError("Error: The merge PDF must contain at least one page.")
        
        # Store the original merge page to create copies later
        original_merge_page = merge_reader.pages[0]

        # The new page will be A4 landscape.
        width = PaperSize.A4.height
        height = PaperSize.A4.width

        for page in reader.pages:
            dest_page = writer.add_blank_page(width=width, height=height)

            # Create a fresh, deep copy of the merge page for this iteration
            merge_page = deepcopy(original_merge_page)

            # Calculate scale factors for the original page
            page_width = page.mediabox.width
            page_height = page.mediabox.height
            x_scale = (width / 2) / page_width
            y_scale = height / page_height
            scale = min(x_scale, y_scale)
            
            # Calculate scale factors for the merge page
            merge_page_width = merge_page.mediabox.width
            merge_page_height = merge_page.mediabox.height
            x_scale_merge = (width / 2) / merge_page_width
            y_scale_merge = height / page_height
            scale_merge = min(x_scale_merge, y_scale_merge)
            
            # Merge the original page with scaling and no translation (it starts at 0,0)
            dest_page.merge_transformed_page(
                page,
                Transformation().scale(scale)
            )
            
            # Merge the merge page with scaling and a horizontal translation to the right half
            dest_page.merge_transformed_page(
                merge_page,
                Transformation().scale(scale_merge).translate(width / 2, 0)
            )
        
        with open(output_pdf_path, "wb") as output_file:
            writer.write(output_file)
        
        print(f"Success: The modified PDF was saved to '{output_pdf_path}'.")
    finally:
        if merge_reader: merge_reader.close()


def resize_pdf(reader, writer, input_pdf_path, output_pdf_path, target_size="A4"):
    """
    Resizes each page of a PDF to a specific paper size, scaling the content
    to fit within the new dimensions.
    Note: input_pdf_path is included for a consistent function signature but not used
    in this specific function, as the reader object is already provided.

    Args:
        reader (PdfReader): The PdfReader object for the input file.
        writer (PdfWriter): The PdfWriter object to write to the output file.
        input_pdf_path (str): The path to the original PDF file.
        output_pdf_path (str): The path where the new PDF will be saved.
        target_size (str, optional): The name of the target paper size from the
                                     PAPER_SIZES dictionary. Defaults to "A4".
    """
    target_dimensions = PAPER_SIZES.get(target_size)
    if not target_dimensions:
        raise ValueError(f"Error: Invalid target size '{target_size}'. "
                         f"Supported sizes are: {', '.join(PAPER_SIZES.keys())}")
    
    target_width, target_height = target_dimensions
    
    for page in reader.pages:
        page_width = page.mediabox.width
        page_height = page.mediabox.height
        
        # Calculate the scale factor to fit the content within the target size
        x_scale = target_width / page_width
        y_scale = target_height / page_height
        scale = min(x_scale, y_scale)
        
        # Create a new blank page with the target dimensions
        dest_page = writer.add_blank_page(width=target_width, height=target_height)
        
        # Merge the original page onto the new page with the calculated scale
        dest_page.merge_transformed_page(
            page,
            Transformation().scale(scale)
        )
        
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Success: The resized PDF was saved to '{output_pdf_path}'.")


def modify_pdf(action, **kwargs):
    """
    A unified function to modify a PDF file.

    Args:
        action (str): The name of the modification function to call.
                      Supported actions: 'duplicate', 'add_notes', 'merge_side_by_side', 'resize'.
        **kwargs: Keyword arguments to be passed to the specific action function.
    """
    actions = {
        'duplicate': duplicate_pdf_pages,
        'add_notes': add_note_margin,
        'merge_side_by_side': merge_pdf_side_by_side,
        'resize': resize_pdf,
    }

    if action not in actions:
        print(f"Error: Invalid action '{action}'. Supported actions are: {', '.join(actions.keys())}")
        return

    # Extract common arguments
    input_pdf_path = kwargs.get('input_pdf_path')
    output_pdf_path = kwargs.get('output_pdf_path')

    # 'resize' action does not require an input_pdf_path, but it's handled by the `resize_pdf` function
    if action != 'resize' and (not input_pdf_path or not output_pdf_path):
        print("Error: 'input_pdf_path' and 'output_pdf_path' are required.")
        return

    reader = None
    writer = None
    try:
        # 'resize' action doesn't require input_pdf_path at this point because it's optional
        if input_pdf_path:
            _verify_paths(input_pdf_path)
            _print_pdf_info(input_pdf_path, "Before Modification")
            reader = PdfReader(input_pdf_path)
        else:
            print("Warning: No input PDF provided. This is only expected for a few actions.")

        writer = PdfWriter()
        
        # Dispatch to the correct function with the shared reader and writer
        actions[action](reader, writer, **kwargs)

    except FileNotFoundError as e:
        print(e)
    except ValueError as e:
        print(f"Error: Invalid argument for action '{action}'. Details: {e}")
    except TypeError as e:
        print(f"Error: Missing or incorrect arguments for action '{action}'. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during action '{action}': {e}")
    finally:
        if reader: reader.close()
        if writer: writer.close()


# --- Example Usage ---
if __name__ == "__main__":
    # Example 1: Duplicate each page of the PDF using the new function
    print("--- Running Example 1: Duplicating pages ---")
    modify_pdf(
        'duplicate',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_duplicated.pdf",
    )
    _print_pdf_info("pdf-files/sample_duplicated.pdf", "After Modification")
    print("\n")

    # Example 2: Demonstrate merging pages side-by-side
    print("--- Running Example 2: Merging pages side-by-side ---")
    modify_pdf(
        'merge_side_by_side',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_merged.pdf",
        merge_pdf_path="pdf-files/merge_page.pdf"
    )
    _print_pdf_info("pdf-files/sample_merged.pdf", "After Modification")
    print("\n")

    # Example 3: Demonstrate adding a thick margin for notes
    print("--- Running Example 3: Adding a thick margin for notes (default 50% margin) ---")
    modify_pdf(
        'add_notes',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_notes_default.pdf",
        background_pdf_path="pdf-files/grid_paper.pdf",
        margin_proportion=0.5
    )
    _print_pdf_info("pdf-files/sample_notes_default.pdf", "After Modification")
    print("\n")

    # Example 4: Demonstrate adding a thick margin for notes (custom 30% margin)
    print("--- Running Example 4: Adding a thick margin for notes (custom 30% margin) ---")
    modify_pdf(
        'add_notes',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_notes_custom.pdf",
        background_pdf_path="pdf-files/grid_paper.pdf",
        margin_proportion=0.3
    )
    _print_pdf_info("pdf-files/sample_notes_custom.pdf", "After Modification")
    print("\n")

    # Example 5: Demonstrate resizing a PDF to a specific size
    print("--- Running Example 5: Resizing PDF to Letter size ---")
    modify_pdf(
        'resize',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_resized.pdf",
        target_size="Letter"
    )
    _print_pdf_info("pdf-files/sample_resized.pdf", "After Modification")
    print("\n")

    # Example 6: Demonstrate error handling for a non-existent file
    print("--- Running Example 6: Demonstrating file not found error ---")
    modify_pdf(
        'duplicate',
        input_pdf_path="pdf-files/non_existent.pdf",
        output_pdf_path="pdf-files/non_existent_output.pdf",
    )
    _print_pdf_info("pdf-files/non_existent_output.pdf", "After Modification")
    print("\n")
    
    # Example 7: Demonstrate error handling for a missing argument
    print("--- Running Example 7: Demonstrating missing argument error ---")
    modify_pdf(
        'merge_side_by_side',
        input_pdf_path="pdf-files/sample.pdf",
        output_pdf_path="pdf-files/sample_merged_error.pdf",
        # merge_pdf_path is intentionally missing here
    )
    _print_pdf_info("pdf-files/sample_merged_error.pdf", "After Modification")
    print("\n")
