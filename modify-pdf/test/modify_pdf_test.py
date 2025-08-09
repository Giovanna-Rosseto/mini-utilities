import os
import sys
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from unittest.mock import patch, Mock
import pytest

# Add the parent directory to the system path to allow module discovery
# This is necessary when running tests from a different directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modify_pdf_multiprocess import PDFModifier


# Define the directory where test files are located
TEST_DIR = os.path.join(os.path.dirname(__file__), 'pdf-files')
INPUT_PDF = os.path.join(TEST_DIR, 'sampleA.pdf')
INPUT_PDF_2 = os.path.join(TEST_DIR, 'sampleB.pdf')
BACKGROUND_PDF = os.path.join(TEST_DIR, 'grid_paper.pdf')
OUTPUT_PDF = os.path.join(TEST_DIR, 'test_output.pdf')

# A fixture to ensure a clean test environment
@pytest.fixture(autouse=True)
def clean_test_environment():
    """
    Cleans up the test output PDF file and ensures the test directory exists.
    """
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_PDF):
        os.remove(OUTPUT_PDF)
    yield  # This is where the test function runs
    if os.path.exists(OUTPUT_PDF):
        os.remove(OUTPUT_PDF)

def create_real_pdf_files():
    """
    Creates two real PDF files for integration testing.
    """
    writer1 = PdfWriter()
    writer1.add_blank_page(width=PaperSize.A4.width, height=PaperSize.A4.height)
    with open(INPUT_PDF, "wb") as f:
        writer1.write(f)
    writer1.close()
    
    writer2 = PdfWriter()
    writer2.add_blank_page(width=PaperSize.A4.width, height=PaperSize.A4.height)
    with open(INPUT_PDF_2, "wb") as f:
        writer2.write(f)
    writer2.close()

class MockPage(Mock):
    """
    A custom mock class that simulates a pypdf PageObject more accurately.
    It provides a dictionary-like interface and necessary attributes/methods.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.internal_dict = {
            '/Contents': Mock(get_data=Mock(return_value=b'')),
            '/Resources': {
                '/ProcSet': ['/PDF', '/Text', '/ImageB', '/ImageC', '/ImageI'],
                '/XObject': {},
                '/Font': {},
            },
            '/Type': '/Page',
            '/Parent': Mock(),
            '/MediaBox': [0, 0, 100, 100],
            '/CropBox': [0, 0, 100, 100],
        }
        self.mediabox = Mock(width=100, height=100)
        self.cropbox = Mock(width=100, height=100)
        self.artbox = Mock(width=100, height=100)
        self.bleedbox = Mock(width=100, height=100)
        self.trimbox = Mock(width=100, height=100)
        self.rotate = 0
        self._reader = Mock()
        self.merge_page = Mock()
        self.merge_transformed_page = Mock()
        self.merge_transformed_page.return_value = None
        self.add_object = Mock()
        self.add_transformation = Mock()
        self.get_contents = Mock(return_value=Mock(read=Mock(return_value=b'')))
        self._get_contents_and_object = Mock(return_value=([b''], Mock()))
        self.get_page_properties = Mock(return_value={})
        self.get_page_content = Mock(return_value=Mock())
        self.copy_page = Mock(return_value=self)
        self.add_transformation.return_value = None
        self.xfa = None # Mocking this attribute prevents an AttributeError

    def get_object(self):
        """Returns the internal dictionary to simulate pypdf's get_object method."""
        return self.internal_dict
    
    def __getitem__(self, key):
        return self.internal_dict[key]

    def get(self, key, default=None):
        return self.internal_dict.get(key, default)

    def add_contents(self, contents):
        self.internal_dict['/Contents'] = contents

def create_mock_page():
    """
    Creates a robust mock page object that simulates a pypdf PageObject.
    """
    return MockPage()


def create_mock_pdf_file():
    """
    Creates a mock PDFWriter object that simulates writing to a file.
    """
    writer = Mock(spec=PdfWriter)
    
    # Create a mock page object that can be returned by add_blank_page
    mock_page = create_mock_page()
    # The merged page will have new dimensions, so we mock those here
    mock_page.mediabox = Mock(width=200, height=100)
    
    writer.add_blank_page.return_value = mock_page
    writer.add_page.return_value = None
    writer.write.return_value = None
    return writer

def test_duplicate_pages_action_with_mock(capsys):
    """
    Test the 'duplicate' action with mock PDF content.
    """
    modifier = PDFModifier(
        input_pdf_path=INPUT_PDF,
        output_pdf_path=OUTPUT_PDF,
        action='duplicate'
    )
    
    # Mock the PdfReader to simulate a PDF with a single page
    mock_reader = Mock(spec=PdfReader)
    mock_reader.pages = [create_mock_page()]
    
    with patch('modify_pdf_multiprocess.PdfReader', return_value=mock_reader):
        with patch('modify_pdf_multiprocess.PdfWriter', return_value=create_mock_pdf_file()):
            # Mock os.path.exists to simulate the input files existing
            with patch('os.path.exists', side_effect=lambda path: path != OUTPUT_PDF):
                modifier.modify_pdf()
                
                captured = capsys.readouterr()
                # Check for a success message and the absence of an error
                assert 'Success' in captured.out
                assert 'Error' not in captured.out

def test_add_notes_margin_action_with_mock(capsys):
    """
    Test the 'add_notes' action with a mock PDF and background.
    """
    modifier = PDFModifier(
        input_pdf_path=INPUT_PDF,
        output_pdf_path=OUTPUT_PDF,
        action='add_notes',
        background_pdf_path=BACKGROUND_PDF,
        margin_proportion=0.25
    )
    
    mock_reader = Mock(spec=PdfReader)
    mock_reader.pages = [create_mock_page()]
    
    with patch('modify_pdf_multiprocess.PdfReader', return_value=mock_reader):
        with patch('modify_pdf_multiprocess.PdfWriter', return_value=create_mock_pdf_file()):
            # Mock os.path.exists to simulate the input files existing
            with patch('os.path.exists', side_effect=lambda path: path != OUTPUT_PDF):
                modifier.modify_pdf()
                
                captured = capsys.readouterr()
                assert 'Success' in captured.out
                assert 'Error' not in captured.out

def test_merge_side_by_side_with_real_pdfs():
    """
    Test the 'merge_side_by_side' action with real PDF files.
    This is an integration test to ensure the actual PDF library functions correctly.
    """
    # Create dummy PDF files for the test
    create_real_pdf_files()

    modifier = PDFModifier(
        input_pdf_path=INPUT_PDF,
        output_pdf_path=OUTPUT_PDF,
        action='merge_side_by_side',
        merge_pdf_path=INPUT_PDF_2
    )
    
    modifier.modify_pdf()

    # Assert that the output file was created
    assert os.path.exists(OUTPUT_PDF)

    # Assert that the output PDF has the expected content and dimensions
    reader_output = PdfReader(OUTPUT_PDF)
    assert len(reader_output.pages) == 1
    page = reader_output.pages[0]
    # Check that the page dimensions are now A4 landscape (the target size)
    assert page.mediabox.width == PaperSize.A4.height
    assert page.mediabox.height == PaperSize.A4.width

def test_resize_pdf_action_with_mock(capsys):
    """
    Test the 'resize' action with a mock PDF.
    """
    modifier = PDFModifier(
        input_pdf_path=INPUT_PDF,
        output_pdf_path=OUTPUT_PDF,
        action='resize',
        target_size='A5_Landscape'
    )

    mock_reader = Mock(spec=PdfReader)
    mock_reader.pages = [create_mock_page()]
    
    with patch('modify_pdf_multiprocess.PdfReader', return_value=mock_reader):
        with patch('modify_pdf_multiprocess.PdfWriter', return_value=create_mock_pdf_file()):
            # Mock os.path.exists to simulate the input files existing
            with patch('os.path.exists', side_effect=lambda path: path != OUTPUT_PDF):
                modifier.modify_pdf()

                captured = capsys.readouterr()
                assert 'Success' in captured.out
                assert 'Error' not in captured.out

def test_nonexistent_input_file_prints_error(capsys):
    """
    Test that a nonexistent input file prints an error message to the console.
    """
    modifier = PDFModifier(
        input_pdf_path="nonexistent.pdf",
        output_pdf_path=OUTPUT_PDF,
        action='duplicate'
    )
    
    # We must explicitly mock os.path.exists to return False for the nonexistent file
    with patch('os.path.exists', side_effect=lambda path: path != "nonexistent.pdf"):
        with patch('modify_pdf_multiprocess.PdfReader'):
            modifier.modify_pdf()
            captured = capsys.readouterr()
            # Assert that the error message is in the captured output
            assert "Error: File not found. Details: Error: The file 'nonexistent.pdf' was not found." in captured.out


def test_invalid_action_prints_error(capsys):
    """
    Test that an invalid action prints an error message to the console.
    """
    modifier = PDFModifier(
        input_pdf_path=INPUT_PDF,
        output_pdf_path=OUTPUT_PDF,
        action='invalid_action'
    )
    
    with patch('os.path.exists', side_effect=lambda path: path != OUTPUT_PDF):
        with patch('modify_pdf_multiprocess.PdfReader'):
            modifier.modify_pdf()
            captured = capsys.readouterr()
            # Assert that the error message is in the captured output
            assert "Error: Invalid action 'invalid_action'" in captured.out
