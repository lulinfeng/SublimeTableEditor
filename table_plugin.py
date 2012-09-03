import sublime, sublime_plugin
import tablelib
import re

#TODO: fix namesace for command names to avoid conflict with other plugins
#TODO: check multiple selection in scope one table

def find(text, sep, num):
    found = -1
    index = 0
    for i in range(num):
        found = text.find(sep,index)
        if index == -1:
            return -1
        index = found + 1
    return found


class AbstractTableCommand(sublime_plugin.TextCommand):

    def get_text(self, row):
        point = self.view.text_point(row,0)
        region = self.view.line(point)
        text = self.view.substr(region)
        return text

    def get_full_text(self, row):
        point = self.view.text_point(row,0)
        region = self.view.full_line(point)
        text = self.view.substr(region)
        return text

    def get_line_num(self, point):
        return self.view.rowcol(point)[0]

    def is_header_line(self, row):
        return re.match(r"^\s*\|([\-]+\|)+$",self.get_text(row)) is not None

    def is_table_line(self, row):
        return re.match(r"^\s*\|",self.get_text(row)) is not None

    def get_field_num(self, row, col):
        field_num = self.get_text(row).count("|", 0, col)
        return field_num - 1

    def get_field_count(self, row):
        return self.get_text(row).count('|') - 1

    def last_line_num(self):
        return self.view.rowcol(self.view.size())[0]

    def get_field_begin_point(self, row, field_num):
        col = find(self.get_text(row), '|', field_num +1 ) + 2
        return self.view.text_point(row,col)

    def nav_field_end_point(self, row, field_num):
        i1 = find(self.get_text(row), '|', field_num +1 )
        i2 = find(self.get_text(row), '|', field_num +2 )
        match = re.compile(r"([^\s])\s+$").search(self.get_text(row),i1 + 1,i2)
        if match:
            return self.view.text_point(row,match.start(1) + 1)
        else:
            return self.view.text_point(row,i2 - 1)

    def nav_field_begin_point(self, row, field_num):
        i1 = find(self.get_text(row), '|', field_num +1 )
        i2 = find(self.get_text(row), '|', field_num +2 )
        match = re.compile(r"([^\s]).*").search(self.get_text(row),i1 + 1,i2)
        if match:
            return self.view.text_point(row,match.start(1))
        else:
            return self.view.text_point(row,i1 + 2)

    def last_table_line_num(self, row):
        assert self.is_table_line(row), "Expected table row"
        last_table_row = row
        last_line = self.last_line_num()
        while (row <= last_line and self.is_table_line(row)):
            last_table_row = row
            row = row + 1
        return last_table_row

    def first_table_line_num(self, row):
        assert self.is_table_line(row), "Expected table row"
        firts_table_row = row
        while (row >= 0 and self.is_table_line(row)):
            firts_table_row = row
            row = row - 1
        return firts_table_row


class AbstractTableMultiSelect(AbstractTableCommand):

    def run(self, edit):
        self.run_before(edit)
        new_sels = []
        for sel in self.view.sel():
            if not self.is_table_line(self.get_line_num(sel.begin())):
                new_sels.append(sel)
                continue
            new_sel = self.run_one_sel(edit,sel)
            new_sels.append(new_sel)

        self.view.sel().clear()
        for sel in new_sels:
            self.view.sel().add(sel)
        self.run_after(edit)

    def run_before(self, edit):
        pass

    def run_after(self, edit):
        pass

    def run_one_sel(self,edit,sel):
        return sel


class TableAlignCommand(AbstractTableMultiSelect):
    """
    Command: table_align
    Key: ctrl+c, ctrl+c
    Re-align the table without change the current table field. Move cursor to begin of the current table field.
    """

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        firts_line = self.first_table_line_num(self.get_line_num(sel.begin()))
        last_line = self.last_table_line_num(self.get_line_num(sel.begin()))

        begin_point = self.view.line(self.view.text_point(firts_line,0)).begin()
        end_point = self.view.line(self.view.text_point(last_line,0)).end()

        table_region = sublime.Region(begin_point,end_point)
        text = self.view.substr(table_region)

        sel_field_num = self.get_field_num(sel_row, sel_col)
        self.view.replace(edit, table_region, tablelib.format_table(text))
        if sel_field_num >= self.get_field_count(sel_row):
            sel_field_num = 0
        pt = self.get_field_begin_point(sel_row, sel_field_num)
        return sublime.Region(pt,pt)


class TableNextField(AbstractTableMultiSelect):
    """
    Command: table_next_field.
    Key: tab
    Re-align the table, move to the next field. Creates a new row if necessary.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)

        if field_num +1 < self.get_field_count(sel_row):
            field_num += 1
        elif sel_row < self.last_table_line_num(sel_row):
            field_num = 0
            sel_row += 1
        else:
            region = self.view.line(sel)
            text = self.get_text(sel_row)
            i1 = find(text, '|', 1)
            new_text = "\n" + text[:i1] + re.sub(r"[^\|]",' ',text[i1:])
            self.view.insert(edit, region.end(),new_text)
            field_num = 0
            sel_row += 1
        pt = self.get_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TablePreviousField(AbstractTableMultiSelect):
    """
    Command: table_previous_field
    Key: shift+tab
    Re-align, move to previous field.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)

        if field_num > 0:
           field_num = field_num -1
        elif sel_row > self.first_table_line_num(sel_row):
            sel_row -= 1
            field_num = self.get_field_count(sel_row) - 1
        pt = self.get_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TableNextRow(AbstractTableMultiSelect):
    """
    Command: table_next_row
    Key: alt + enter, enter
    Re-align the table and move down to next row. Creates a new row if necessary.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)
        if sel_row < self.last_table_line_num(sel_row):
            sel_row += 1
        else:
            line_region = self.view.line(sel)
            text = self.get_text(sel_row)
            i1 = find(text, '|', 1)
            new_text = "\n" + text[:i1] + re.sub(r"[^\|]",' ',text[i1:])
            self.view.insert(edit, line_region.end(),new_text)
            sel_row += 1
        pt = self.get_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TableBeginningOfField(AbstractTableMultiSelect):
    """
    Command: table_beginning_of_field
    Key: ctrl+left
    Move to beginning of the current table field.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)
        pt = self.nav_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TableEndOfField(AbstractTableMultiSelect):
    """
    Command: table_end_of_field
    Key: ctrl+right
    Move to end of the current table field.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)
        pt = self.nav_field_end_point(sel_row, field_num)
        return sublime.Region(pt,pt)



class TableMoveColumnLeft(AbstractTableMultiSelect):
    """
    Command: table_move_column_left
    Key: alt+left
    Move the current column right.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)
        if field_num == 0:
            return sel
        start_row = self.first_table_line_num(sel_row)
        end_row = self.last_table_line_num(sel_row)
        row = start_row
        while row <= end_row:
            text = self.get_text(row)
            i1 = find(text, '|', field_num + 0)
            i2 = find(text, '|', field_num + 1)
            i3 = find(text, '|', field_num + 2)
            new_text = text[0:i1] + text[i2:i3] + text[i1:i2] + text[i3:]
            self.view.replace(edit,
                            self.view.line(self.view.text_point(row, sel_col)),
                            new_text
                            )
            row += 1
        pt = self.get_field_begin_point(sel_row, field_num - 1)
        return sublime.Region(pt,pt)



class TableMoveColumnRight(AbstractTableMultiSelect):
    """
    Command: table_move_column_right
    Key: alt+right
    Move the current column right.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)
        if field_num == self.get_field_count(sel_row) - 1:
            return sel
        start_row = self.first_table_line_num(sel_row)
        end_row = self.last_table_line_num(sel_row)
        row = start_row

        while row <= end_row:
            text = self.get_text(row)
            i1 = find(text, '|', field_num + 1)
            i2 = find(text, '|', field_num + 2)
            i3 = find(text, '|', field_num + 3)
            new_text = text[0:i1] + text[i2:i3] + text[i1:i2] + text[i3:]
            self.view.replace(edit,
                            self.view.line(self.view.text_point(row, sel_col)),
                            new_text
                            )
            row += 1
        pt = self.get_field_begin_point(sel_row, field_num + 1)
        return sublime.Region(pt,pt)



class TableDeleteColumn(AbstractTableMultiSelect):
    """
    Command: (table_delete_column)
    Key: alt+shift+left
    Kill the current column.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)

        start_row = self.first_table_line_num(sel_row)
        end_row = self.last_table_line_num(sel_row)
        row = start_row
        field_count = self.get_field_count(sel_row)
        while row <= end_row:
            text = self.get_text(row)
            i1 = find(text, '|', field_num + 1)
            i2 = find(text, '|', field_num + 2)
            if field_count > 1:
                self.view.replace(edit,
                                self.view.line(self.view.text_point(row, sel_col)),
                                text[0:i1] + text[i2:])
            else:
                self.view.replace(edit,
                                self.view.line(self.view.text_point(row, sel_col)),
                                text[0:i1] + text[i2+1:])

            row += 1
        if field_num == self.get_field_count(sel_row):
            field_num -= 1
        pt = self.get_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TableInsertColumn(AbstractTableMultiSelect):
    """
    Command: table_insert_column
    Keys: alt+shift+right
    Insert a new column to the left of the cursor position.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        field_num = self.get_field_num(sel_row, sel_col)

        start_row = self.first_table_line_num(sel_row)
        end_row = self.last_table_line_num(sel_row)
        row = start_row
        field_count = self.get_field_count(sel_row)
        while row <= end_row:
            text = self.get_text(row)
            cell = "   "
            if self.is_header_line(row):
                cell = "---"
            i1 = find(text, '|', field_num + 1)
            self.view.replace(edit,
                            self.view.line(self.view.text_point(row, sel_col)),
                            text[0:i1] + "|" + cell + text[i1:])

            row += 1
        pt = self.get_field_begin_point(sel_row, field_num)
        return sublime.Region(pt,pt)


class TableKillRow(AbstractTableMultiSelect):
    """
    Command: table_kill_row
    Key : alt+shift+up
    Kill the current row or horizontal line.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        first_row = self.first_table_line_num(sel_row)
        last_row = self.last_table_line_num(sel_row)
        self.view.erase(edit, self.view.full_line(sel))
        if sel_row == last_row :
            sel_row = sel_row - 1
        if not self.is_table_line(sel_row):
            sel_col = 0
        pt = self.view.text_point(sel_row, sel_col)
        return sublime.Region(pt,pt)

class TableInsertRow(AbstractTableMultiSelect):
    """
    Command: table_insert_row
    Key: alt+shift+down
    Insert a new row above the current row.
    """

    def run_before(self,edit):
        self.view.run_command("table_align")

    def run_one_sel(self, edit,sel):
        (sel_row, sel_col) = self.view.rowcol(sel.begin())
        line_region = self.view.line(sel)
        text = self.view.substr(line_region)
        i1 = find(text, '|', 1)
        new_text = text[:i1] + re.sub(r"[^\|]",' ',text[i1:]) + "\n"
        self.view.insert(edit, line_region.begin(),new_text)
        pt = self.view.text_point(sel_row, sel_col)
        return sublime.Region(pt,pt)

