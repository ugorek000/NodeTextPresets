#24.03.22 by ugorek

import bpy

def prop_inac(self, *args, **kw_args):
    self.prop(*args, **kw_args)
    self.active = False
bpy.types.UILayout.prop_inac = prop_inac #Гениально. Но юзабельно в основном с внешним ly.ly(stuff).prop_inac().
prop_inac.__doc__ = f'''Utility from "{__name__}.py" module'''

def operator_props(self, operator, text="", text_ctxt="", translate=True, icon='NONE', emboss=True, depress=False, icon_value=0, **kw_args):
    op = self.operator(operator, text=text, text_ctxt=text_ctxt, translate=translate, icon=icon, emboss=emboss, depress=depress, icon_value=icon_value)
    for dk, dv in kw_args.items():
        setattr(op, dk, dv)
    #return op
bpy.types.UILayout.operator_props = operator_props
operator_props.__doc__ = f'''Utility from "{__name__}.py" module'''

#Заметка: Если в названии есть Add -- функция возвращает макет.

def LyBoxAsLabel(where, txt, *, active=True):
    box = where.box()
    row = box.row(align=True)
    row.alignment = 'CENTER'
    row.label(text=txt)
    row.active = active
    box.scale_y = 0.5
def LyAddHeaderedBox(where, txt, *, active=True):
    col = where.column(align=True)
    if txt:
        LyBoxAsLabel(col, txt, active=active)
    return col.box()

import rna_keymap_ui
def LySimpleKeyMapList(context, where, kmU, set_opBlids):
    #import rna_keymap_ui
    colMain = where.column(align=True)
    #colMain.separator()
    rowLabelRoot = colMain.row(align=True)
    rowLabelText = rowLabelRoot.row(align=True)
    rowLabelText.alignment = 'LEFT'
    rowLabelText.label(icon='DOT')
    rowLabelText.label(text=kmU.name)
    rowLabelPost = rowLabelRoot.row(align=True)
    rowLabelPost.active = False
    if kmU.is_user_modified:
        rowRestore = rowLabelRoot.row(align=True)
        rowRestore.context_pointer_set('keymap', kmU)
        rowRestore.operator('preferences.keymap_restore', text="Restore")
    colList = colMain.row().column(align=True)
    sco = 0
    for li in reversed(kmU.keymap_items):
        if li.idname in set_opBlids:
            colList.context_pointer_set('keymap', kmU)
            rna_keymap_ui.draw_kmi([], context.window_manager.keyconfigs.user, kmU, li, colList, 0)
            sco += 1
    rowLabelPost.label(text=f"({sco})")

import traceback
class TryAndErrInLy():
    def __init__(self, where):
        self.ly = where
    def __enter__(self):
        return self.ly
    def __exit__(self, type, value, tb):
        #import traceback
        if type: #any((type, value, tb))
            row = self.ly.row(align=True)
            row.label(icon='ERROR')
            col = row.column(align=True)
            for li in traceback.format_exc().split("\n")[:-1]:
                col.label(text=li)

def LyNiceColorProp(where, ess, prop, align=False, text="", decor=3):
    rowCol = where.row(align=align)
    rowLabel = rowCol.row()
    rowLabel.alignment = 'LEFT'
    rowLabel.label(text=text if text else ess.bl_rna.properties[prop].name+":")
    rowLabel.active = decor%2
    rowProp = rowCol.row()
    rowProp.alignment = 'EXPAND'
    rowProp.prop(ess, prop, text="")
    rowProp.active = decor//2%2

def LyHighlightingText(where, *args_txt):
    rowRoot = where.row(align=True)
    for cyc, txt in enumerate(args_txt):
        if txt:
            row = rowRoot.row(align=True)
            row.alignment = 'LEFT'
            row.label(text=txt)
            row.active = cyc%2