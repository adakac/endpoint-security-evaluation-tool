# Functions for reading and writing data to and from the ODS file.
from odf.opendocument import load, OpenDocument
from odf.table import Table, TableRow, TableCell
from odf.namespaces import OFFICENS, TABLENS
from odf.text import P
from constants import *
from table_definitions import *
from sqlalchemy import Sequence



'''
=====================================================================================
| Custom Exception that will be raised if there's a problem with the ODS file.      |
=====================================================================================
'''
class ODSException(Exception):
    pass



'''
=====================================================================================
| Helper class for managing reading and writing to ODS files.                       |
=====================================================================================
'''
class ODSHandler():
    
    def __init__(self, file_path: str, sheet_name: str, db: Session):
        self.file_path: str = file_path
        self.doc: OpenDocument = load(file_path)
        self.sheet: Table = self.get_sheet(sheet_name)

        # ODS row objects for directly manipulating the file.
        self.rows_ods = self.sheet.getElementsByType(TableRow)

        # Row values, only for reading.
        self.rows: dict = self.read_rows(col_limit=25)

        # Cleaning up empty rows and cells.
        self.remove_empty_cells()
        self.remove_empty_rows()
        self.expand_cells()

        self.db: Session = db


    '''
    =====================================================================================
    | Searches and returns a Worksheet in the Workbook by name.                         |
    =====================================================================================
    '''
    def get_sheet(self, sheet_name: str) -> Table:
        for table in self.doc.spreadsheet.getElementsByType(Table):
            if table.getAttribute("name") == sheet_name:
                return table
        
        raise ODSException(f"Worksheet \"{sheet_name}\" not found.")



    '''
    =====================================================================================
    | Reads all rows from the worksheet and returns it as a list of lists.              |
    =====================================================================================
    '''
    def read_rows(self, col_limit: int) -> dict:
        # Use a hashtable instead of a list for faster lookups.
        rows = {}

        for row_index, row in enumerate(self.sheet.getElementsByType(TableRow)):
            row_data = []

            col_count = 0
            for cell in row.getElementsByType(TableCell):
                # If the same cell is repeated x times, odf doesn't store the value x times, it only stores how often the cell is repeated.
                # None means it's repeated 1 times.
                repeat_cell = int(cell.getAttribute("numbercolumnsrepeated") or 1)

                # If the col_limit is reached, only repeat the remaning cols up to col_limit.
                col_remaining = col_limit - col_count
                col_count += repeat_cell
                
                if col_count > col_limit:
                    repeat_cell = col_remaining

                # All numbers in ods are stored as float, but we only use integers.
                if cell.getAttribute("valuetype") == "float":
                    value = float(cell.getAttribute("value"))
                    value = int(value)
                
                # Texts are stored as Type "P". There can be multiple paragraphs per cell.
                else:
                    value = " ".join(str(p) for p in cell.getElementsByType(P))

                row_data.extend([value] * repeat_cell)

            # Fill up to col_limit to avoid index errors.
            while len(row_data) < col_limit:
                row_data.append("")

            # Populate the hashtable and use the MITRE-ID as key.
            mitre_id = row_data[COL_MITREID]
            rows[mitre_id] = {"row_data": row_data, "row_index": row_index}
        
        return rows



    '''
    =====================================================================================
    | Modifies an existing cell in the Worksheet by Row and Column Index.               |
    | E.g. Column=3 and Row=2 --> Cell D3                                               |
    =====================================================================================
    '''
    def set_cell(self, row_index: int, col_index: int, value: int|float|str) -> None:
        rows = self.rows_ods

        # Automatically expand the document if row_index is out of bounds by adding rows to the document.
        while len(rows) <= row_index:
            new_row = TableRow()
            self.sheet.addElement(new_row)
            rows.append(new_row)

        target_row = rows[row_index]
        target_row.setAttribute("numberrowsrepeated", 1)

        # Automatically expand the document if col_index is out of bounds by addings cells to the row.
        cells = target_row.getElementsByType(TableCell)
        while len(cells) <= col_index:
            new_cell = TableCell()
            target_row.addElement(new_cell)
            cells.append(new_cell)
        
        target_cell = cells[col_index]
        target_cell.setAttribute("numbercolumnsrepeated", 1)
        
        # Remove all existing childnodes (e.g. P nodes for text).
        target_cell.childNodes[:] = []

        # Remove all attributes that could contain values and datatypes. All previous content of the cell will be removed including the datatype.
        for attr in ("value", "string-value", "date-value", "boolean-value", "time-value", "currency", "value-type"):
            key = (OFFICENS, attr)
            if key in target_cell.attributes:
                del target_cell.attributes[key]
        
        # Delete all value and value-type keys from other namespaces (this typically happens when converting from xlsx to ods).
        for key in list(target_cell.attributes):
            ns, name = key
            if name == "value-type":
                del target_cell.attributes[key]
        
        # Remove formulas in the cell.
        key = (TABLENS, "formula")
        if key in target_cell.attributes:
            del target_cell.attributes[key]

        # ODS uses float for all numbers.
        if isinstance(value, (int, float)):
            # Set the attribute to float. This tells ODS how to display the value.
            target_cell.setAttribute("valuetype", "float")
            target_cell.setAttribute("value", float(value))

            # Even though it is a number, the text is stored as string. The valuetype attribute tells ODS however
            # how to display this value. There's a difference between how it is stored and how it is displayed.
            target_cell.addElement(P(text=str(value)))
        
        # Treat all other values as string.
        else:
            target_cell.setAttribute("valuetype", "string")
            target_cell.addElement(P(text=str(value)))
    

    '''
    =====================================================================================
    | Adds a new row to the end of the document.                                        |
    =====================================================================================
    '''
    def append_row(self, values: list) -> None:
        new_row = TableRow()

        # Populate the row with values.
        for value in values:
            cell = TableCell()

            if isinstance(value, (int, float)):
                cell.setAttribute("valuetype", "float")
                cell.setAttribute("value", float(value))
                cell.addElement(P(text=str(value)))
            else:
                cell.setAttribute("valuetype", "string")
                cell.addElement(P(text=str(value)))
            
            new_row.addElement(cell)
        
        self.sheet.addElement(new_row)



    '''
    =====================================================================================
    | Checks if all cells in a row are empty.                                           |
    =====================================================================================
    '''
    @staticmethod
    def is_row_empty(row: TableRow) -> bool:
        for cell in row.getElementsByType(TableCell):
            
            # If the cell has any child nodes (like <text:p>), it is not empty.
            if cell.childNodes:
                return False
            
            # If the cell has a value attribute it is not empty.
            if cell.getAttribute("value"):
                return False
            
        return True
    
    '''
    =====================================================================================
    | Removes all lines without any content.                                            |
    |                                                                                   |
    | Somehow our ODS file has lots of empty rows which can cause problems once they    |
    | reach the row limit (~ 1.000.000).                                                |
    |                                                                                   |
    | If the row limit is reached no new rows can be added without corrupting the file. |
    =====================================================================================
    '''
    def remove_empty_rows(self):
        # Remove from bottom to top, so there are no problems to remove rows while iterating over them.
        for row in reversed(self.rows_ods):
            if self.is_row_empty(row):
                self.sheet.removeChild(row)
        
        # Update the variable by reading the updated rows.
        self.rows_ods = self.sheet.getElementsByType(TableRow)

    

    '''
    =====================================================================================
    | Removes empty cells in a document when they are repeated more than 10 times.      |
    | This prevents lots of empty cells in a row.                                       |
    |                                                                                   |
    | Somehow our ODS file has so many empty cells that it reaches the column limit     |
    | (~ 16.000).                                                                       |
    |                                                                                   |
    | If the column limit is reached no further columns can be added and the ODS file   |
    | will be left in a corrupt state.                                                  |
    =====================================================================================
    '''
    def remove_empty_cells(self):
        for row in self.rows_ods:
            cells_to_remove = []
            cells = row.getElementsByType(TableCell)
            for cell in cells:
                repeated = int(cell.getAttribute("numbercolumnsrepeated") or 1)

                # If more than 10 empty cells in a row.
                if repeated > 10 and not cell.childNodes:
                    cells_to_remove.append(cell)
        
            for cell in cells_to_remove:
                row.removeChild(cell)
        
        # Update the variable.
        self.rows_ods = self.sheet.getElementsByType(TableRow)



    '''
    =====================================================================================
    | Expand all cells that have "numbercolumnsrepeated" set to 2 or higher.            |
    |                                                                                   |
    | When x cells have the same value, ODS only creates one cell in the XML structure  |
    | but sets "numbercolumnsrepeated" to x, so the Reader knows how often to display   |
    | the same cell.                                                                    |
    |                                                                                   |
    | This leads to problems when using indices. For example: One cell does not have    |
    | "numbercolumnsrepeated" but the second one has "numbercolumnsrepeated" set to     |
    | two. This means there are two cells in the XML structure, but the ODS reader      |
    | displays three cells. Because there are only two cells in the XML structure,      |
    | calling cells[0] and cells[1] is valid, but cells[2] is not.                      |
    |                                                                                   |
    | This function fixes this by expanding repeated cells. This means for every cell   |
    | in the ODS Reader there is one cell in the XML structure of the file.             |
    =====================================================================================
    '''
    def expand_cells(self):
        for row in self.rows_ods:
            cells = row.getElementsByType(TableCell)
            new_cells = []

            for cell in cells:
                repeat = int(cell.getAttribute("numbercolumnsrepeated") or 1)

                # Avoid expanding large cells (bigger than 10) and cells that are only repeated once.
                new_cells.append(cell)
                if repeat == 1 or repeat > 10:
                    continue
                
                # Set repeat to 1.
                cell.setAttribute("numbercolumnsrepeated", 1)

                # Expand and copy all repeated cells. Leave the expanded cells empty.
                for _ in range(repeat-1):
                    new_cell = TableCell()
                    new_cells.append(new_cell)

            # Remove all cells that were there before...
            for old_cell in cells:
                row.removeChild(old_cell)
            
            # ...and add the copies and expanded cells.
            for new_cell in new_cells:
                row.addElement(new_cell)



    '''
    =====================================================================================
    | Match all techniques in the change database against the ODS file. If a technique  |
    | from the database is found in the ods file, import it's values. If a technique    |
    | is not found, all values are set to default.                                      |
    =====================================================================================
    '''
    def import_ods(self, changes: Sequence[MITREChange]):
        for c in changes:
            # If a technique is not in the .ods file, set everything to their default value.
            if c.mitre_id not in self.rows:
                # Client scores.
                c.client_criticality, c.client_criticality_sum = 0, 0
                c.client_evaluation_status = "not evaluated"
                c.client_reasoning, c.client_measures = "", ""

                # Infrastructures scores.
                c.infra_criticality, c.infra_criticality_sum = 0, 0
                c.infra_evaluation_status = "not evaluated"
                c.client_reasoning, c.client_measures = "", ""

                # Service scores.
                c.service_criticality, c.service_criticality_sum = 0, 0
                c.service_evaluation_status = "not evaluated"
                c.client_reasoning, c.client_measures = "", ""

                # CIA
                c.confidentiality, c.integrity, c.availability = False, False, False
            
            # Else import the data from the row in the .ods file.
            else:
                row = self.rows[c.mitre_id].get("row_data")

                # Client Scores.
                c.client_criticality = 0 if row[COL_CLIENT_CRITICALITY] == "n.a." else row[COL_CLIENT_CRITICALITY]
                c.client_criticality_sum = 0 if row[COL_CLIENT_CRITICALITY_SUM] == "n.a." else row[COL_CLIENT_CRITICALITY_SUM]
                c.client_evaluation_status = "n.a." if c.client_criticality == 0 else row[COL_CLIENT_EVALUATION_STATUS]
                c.client_reasoning = row[COL_CLIENT_REASONING]
                c.client_measures = row[COL_CLIENT_MEASURES]

                # Infrastructure scores.
                c.infra_criticality = 0 if row[COL_INFRASTRUCTURE_CRITICALITY] == "n.a." else row[COL_INFRASTRUCTURE_CRITICALITY]
                c.infra_criticality_sum = 0 if row[COL_INFRASTRUCTURE_CRITICALITY_SUM] == "n.a." else row[COL_INFRASTRUCTURE_CRITICALITY_SUM]
                c.infra_evaluation_status = "n.a." if c.infra_criticality == 0 else row[COL_INFRASTRUCTURE_EVALUATION_STATUS]
                c.infra_reasoning = row[COL_INFRASTRUCTURE_REASONING]
                c.infra_measures = row[COL_INFRASTRUCTURE_MEASURES]

                # Service scores.
                c.service_criticality = 0 if row[COL_SERVICE_CRITICALITY] == "n.a." else row[COL_SERVICE_CRITICALITY]
                c.service_criticality_sum = 0 if row[COL_SERVICE_CRITICALITY_SUM] == "n.a." else row[COL_SERVICE_CRITICALITY_SUM]
                c.service_evaluation_status = "n.a." if c.service_criticality == 0 else row[COL_SERVICE_EVALUATION_STATUS]
                c.service_reasoning = row[COL_SERVICE_REASONING]
                c.service_measures = row[COL_SERVICE_MEASURES]

                # CIA
                # If "x" then True, else False.
                c.confidentiality = row[COL_CONFIDENTIALITY] == "x"
                c.integrity = row[COL_INTEGRITY] == "x"
                c.availability = row[COL_AVAILABILITY] == "x"
        
        self.db.commit()



    '''
    =====================================================================================
    | Small helper function that aligns a change with the headers of the ODS file.      |
    =====================================================================================
    '''
    @staticmethod
    def create_row(change: MITREChange) -> list:
        return ["", change.mitre_id, change.tactics, change.technique, change.sub_technique,
            change.client_criticality, change.infra_criticality, change.service_criticality,
            "x" if change.confidentiality else "",
            "x" if change.integrity else "",
            "x" if change.availability else "",
            change.client_criticality_sum,
            change.client_evaluation_status, "",
            change.client_reasoning,
            change.client_measures,
            "",
            change.infra_evaluation_status, "",
            change.infra_reasoning,
            change.infra_measures, "",
            change.service_evaluation_status,
            change.service_reasoning,
            change.service_measures
        ]



    '''
    =====================================================================================
    | This function exports the SQLite database and all changes made during the upgrade |
    | back into the ODS file and saves it on the local disk.                            |
    | Additions cannot be added because ODS always leaves the file in a corrupt state   |
    | when new rows are added.                                                          |
    =====================================================================================
    '''
    def export_ods(self, file_path: str, changes: Sequence[MITREChange]):
        for c in changes:
            # If a row doesn't exist append it (e.g. new techniques).
            if c.mitre_id not in self.rows:
                self.append_row(self.create_row(c))
            
            # Only export techniques with 0 sub-techniques.
            else:
                row_index = self.rows[c.mitre_id].get("row_index")

                self.set_cell(row_index, COL_CLIENT_CRITICALITY, c.client_criticality)
                self.set_cell(row_index, COL_CLIENT_EVALUATION_STATUS, c.client_evaluation_status)
                self.set_cell(row_index, COL_CLIENT_REASONING, c.client_reasoning)
                self.set_cell(row_index, COL_CLIENT_MEASURES, c.client_measures)

                # Infrastructure Scores.
                self.set_cell(row_index, COL_INFRASTRUCTURE_CRITICALITY, c.infra_criticality)
                self.set_cell(row_index, COL_INFRASTRUCTURE_EVALUATION_STATUS, c.infra_evaluation_status)
                self.set_cell(row_index, COL_INFRASTRUCTURE_REASONING, c.infra_reasoning)
                self.set_cell(row_index, COL_INFRASTRUCTURE_MEASURES, c.infra_measures)

                # Service Scores.
                self.set_cell(row_index, COL_SERVICE_CRITICALITY, c.service_criticality)
                self.set_cell(row_index, COL_SERVICE_EVALUATION_STATUS, c.service_evaluation_status)
                self.set_cell(row_index, COL_SERVICE_REASONING, c.service_reasoning)
                self.set_cell(row_index, COL_SERVICE_MEASURES, c.service_measures)

                # CIA
                self.set_cell(row_index, COL_CONFIDENTIALITY, "x" if c.confidentiality else "")
                self.set_cell(row_index, COL_INTEGRITY, "x" if c.integrity else "")
                self.set_cell(row_index, COL_AVAILABILITY, "x" if c.availability else "")
        
        self.doc.save(file_path)