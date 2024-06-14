bl_info = {'name':"NodeTextPresets", 'author':"ugorek",
           'version':(2,0,2), 'blender':(4,1,1), 'created':"2024.06.15",
           'description':"", 'location':"",
           'warning':"", 'category':"Node",
           'tracker_url':"https://github.com/ugorek000/NodeTextPresets/issues", 'wiki_url':""}
#№№ as package

from builtins import len as length
import bpy, re, time, os, subprocess

if __name__!="__main__":
    import sys
    assert __file__.endswith("__init__.py")
    sys.path.append(__file__[:-11])

import opa
import uu_ly

class OpSimpleExec(bpy.types.Operator):
    bl_idname = 'ntp.simple_exec'
    bl_label = "OpSimpleExec"
    bl_options = {'UNDO'}
    exc: bpy.props.StringProperty(name="Exec", default="")
    def invoke(self, context, event):
        exec(self.exc)
        return {'FINISHED'}

class NtpData:
    dict_whereOpened = {}
    txtErrorInLoad = ""
    dict_presets = {}
    @staticmethod
    def GetKeyForDictWo(context):
        return (context.area, context.space_data.tree_type) #context.space_data при CtrlZ будет другим.

def GetTextPresetFromTree(tree):
    def GetPresetNodeAsText(ndTar):
        def GetNdDifferenceAsText(essTar, essRef, txt_format, *, set_ignoredProps): #https://github.com/ugorek000/NodeHotPie (ныне ещё не существующий на 24.03.29)
            result = ""
            if (essTar.bl_idname=='NodeReroute')and(essTar.width==16.0):
                set_ignoredProps.add('width')
            occ = False
            for dk, dv in essTar.bl_rna.properties.items():
                if (not dv.is_readonly)and(dk not in set_ignoredProps):
                    if not hasattr(essRef, dk):
                        assert not "alert"
                        continue
                    valTar = getattr(essTar, dk)
                    valRef = getattr(essRef, dk)
                    if (dv.type in {'FLOAT','INT'})and(dv.is_array):
                        valTar = valTar[:]
                        valRef = valRef[:]
                    if valTar!=valRef:
                        val = valTar
                        match dv.type:
                            case 'ENUM':
                                val = "'%s'"%val
                            case 'STRING':
                                val = "\"%s\""%val
                            case 'POINTER':
                                if dk=='parent':
                                    val = repr(val)
                                elif essTar.type=='GROUP':
                                    val = "\"%s\""%essTar.node_tree.name
                                elif issubclass(dv.fixed_type.__class__, bpy.types.ID):
                                    val = repr(val).replace("['%s']"%val.name, ".get(\"%s\")"%val.name)
                        result += ", "*occ+txt_format.format(**locals())
                        occ = True
                    setattr(essRef, dk, valTar) #Для перечислений, https://projects.blender.org/blender/blender/commit/8149678d5e1d6e0d00668c3f209736721401b4e9
            return result
        dict_result = {}
        ##
        ndRef = ndTar.id_data.nodes.new(ndTar.bl_idname)
        dict_result["props"] = GetNdDifferenceAsText(ndTar, ndRef, "'{dk}':{val}", set_ignoredProps={'name', 'select', 'show_texture', 'is_active_output', 'active_item'})
        dict_sockets = dict_result.setdefault("sockets", {})
        for cyc0, puts in enumerate(('inputs','outputs')):
            dir = cyc0*2-1
            for cyc1, (skTar, skRef) in enumerate( zip(getattr(ndTar, puts), getattr(ndRef, puts)) ):
                dict_sockets[dir*(cyc1+1)] = GetNdDifferenceAsText(skTar, skRef, "'{dk}':{val}", set_ignoredProps={'display_shape', 'enabled', 'bl_label', 'bl_idname', 'bl_subtype_label'})
        ndTar.id_data.nodes.remove(ndRef)
        ##
        def RecrDictToText(dict_recr):
            result = ""
            occ = False
            for dk, dv in dict_recr.items():
                if (dv)and(txt:=RecrDictToText(dv) if dv.__class__==dict else dv):
                    result += ", "*occ+repr(dk).replace("'","\"")+":{"+txt+"}"
                    occ = True
            return result
        txt_result = "('%s',{ %s })"%(ndTar.bl_idname, RecrDictToText(dict_result))
        return txt_result.replace("  ","")
    def GetSocketIndex(sk):
        return int(sk.path_from_id().split(".")[-1].split("[")[-1][:-1])
    txt_result = "{\"tree\":\"%s\", \"nodes\":["%tree.bl_idname
    dict_ndIndex = {}
    locRoot = tree.nodes.active.location.copy()
    occ = False
    sco = 0
    for nd in tree.nodes:
        if nd.select:
            bNd = opa.BNode(nd)
            bNd.locx -= locRoot.x
            bNd.locy -= locRoot.y
            txt_result += ", "*occ+GetPresetNodeAsText(nd)
            bNd.locx += locRoot.x
            bNd.locy += locRoot.y
            dict_ndIndex[nd] = sco
            occ = True
            sco += 1
    txt_result += "], \"links\":["
    occ = False
    for lk in tree.links:
        if (lk.from_node.select)and(lk.to_node.select):
            txt_result += ", "*occ+f"({dict_ndIndex[lk.from_node]}, {GetSocketIndex(lk.from_socket)}, {dict_ndIndex[lk.to_node]}, {GetSocketIndex(lk.to_socket)})"
            occ = True
    return txt_result+"]}"

def AddPresetToTree(tree, dict_preset):
    #Что-то кривит `context.space_data.cursor_location_from_region(event.mouse_x, event.mouse_y)` для чтения из context.space_data.cursor_location, поэтому через костыль:
    bpy.ops.node.add_node('INVOKE_DEFAULT', type='NodeReroute')
    center = tree.nodes.active.location[:]
    tree.nodes.remove(tree.nodes.active)
    ##
    list_nodes = []
    for li in dict_preset['nodes']:
        nd = tree.nodes.new(li[0])
        ##
        for dk, dv in li[1].items():
            match dk:
                case "props":
                    for dk, dv in dv.items():
                        if dk=='node_tree':
                            dv = bpy.data.node_groups.get(dv)
                        setattr(nd, dk, dv)
                case "sockets":
                    tgl = li[0]=='NodeReroute'
                    for dk, dv in dv.items():
                        sk = (nd.inputs if dk<0 else nd.outputs)[abs(dk)-1]
                        for dk, dv in dv.items():
                            if (tgl)and(dk=='default_value'):
                                continue
                            setattr(sk, dk, dv)
        ##
        bNd = opa.BNode(nd)
        bNd.locx += center[0]
        bNd.locy += center[1]
        list_nodes.append(nd)
    for li in dict_preset['links']:
        tree.links.new(list_nodes[li[0]].outputs[li[1]], list_nodes[li[2]].inputs[li[3]])
    return list_nodes

def ProcPresetFile(prefs, action, *, name="", data=""):
    txtFile = prefs.pathToPresetFile
    assert (action=="Load")or(not NtpData.txtErrorInLoad)
    match action:
        case "Load": #Заметка: в остальных действиях нет try, потому что они вызывают "Load".
            try: #(os.path.isfile(txtFile))and(os.path.exists(txtFile))
                with open(txtFile, "r") as file:
                    NtpData.dict_presets = eval("{"+",".join(file.read().splitlines())+"}")
                    for dk, dv in NtpData.dict_presets.items():
                        NtpData.dict_presets[dk] = {'text':dv, 'eval':eval(dv)}
                    NtpData.txtErrorInLoad = ""
            except Exception as ex:
                NtpData.txtErrorInLoad = str(ex)
        case "Save": #Заметка: Используется, как внутренняя функция.
            with open(txtFile, "w") as file:
                #file.write("".join( f"\"{dk}\":\"%s\"\n"%dv['text'].replace("\"","\\\"") for dk, dv in NtpData.dict_presets.items() ))
                file.write("".join( f'"{dk}":"""%s"""\n'%dv['text'] for dk, dv in NtpData.dict_presets.items() )) #"\"{dk}\":\"\"\"%s\"\"\"\n"
        case "Append":
            #with open(txtFile, "a") as file: file.write(data+"\n")
            ProcPresetFile(prefs, "Load")
            NtpData.dict_presets[name] = {'text':data}#,'eval':None}
            ProcPresetFile(prefs, "Save")
        case "Remove":
            ProcPresetFile(prefs, "Load")
            if not NtpData.txtErrorInLoad:
                del NtpData.dict_presets[name]
                ProcPresetFile(prefs, "Save")

def UpdatePathToPresetFile(self, context):
    if UpdatePathToPresetFile.__dict__.setdefault("tgl", False):
        return
    UpdatePathToPresetFile.tgl = True
    self.pathToPresetFile = self.pathToPresetFile.strip("\"")
    ProcPresetFile(self, "Load")
    UpdatePathToPresetFile.tgl = False

class NtpOp:
    def TogglePanelOp(context):
        """Toggle visibility of Panel"""
        key = NtpData.GetKeyForDictWo(context)
        if NtpData.dict_whereOpened.setdefault(key, 0)<2:
            NtpData.dict_whereOpened[key] = 1-NtpData.dict_whereOpened[key]
        if NtpData.dict_whereOpened[key]:
            ProcPresetFile(Prefs(), "Load")
    def TogglePinOp(context):
        """Toggle pinned of Panel"""
        key = NtpData.GetKeyForDictWo(context)
        if NtpData.dict_whereOpened.setdefault(key, 0):
            NtpData.dict_whereOpened[key] = 3-NtpData.dict_whereOpened[key]
    def CopyDiffOp(context, event):
        """Copy selected nodes as raw preset"""
        tree = context.space_data.edit_tree
        if (aNd:=tree.nodes.active)and(aNd.select):
            text = GetTextPresetFromTree(tree)
            if event.shift:
                text =  f"\"{Prefs().nameOfPresetToExport}\":\""+txt.replace("\"","\\\"")+"]}\","
            context.window_manager.clipboard = text
    def OpenFolderOp():
        """Open folder of presets file"""
        #subprocess.Popen(f"explorer /select,\"{Prefs().pathToPresetFile}\"")
        os.startfile(os.path.dirname(Prefs().pathToPresetFile))
    def ReloadOp():
        """Reload all from file"""
        ProcPresetFile(Prefs(), "Load")
    def ExportOp(context):
        """Export with overwriting"""
        prefs = Prefs()
        tree = context.space_data.edit_tree
        if (aNd:=tree.nodes.active)and(aNd.select)and(name:=prefs.nameOfPresetToExport):
            ProcPresetFile(prefs, "Append", name=name, data=GetTextPresetFromTree(tree))
            prefs.nameOfPresetToExport = ""
            ProcPresetFile(prefs, "Load")
    def DelPresetOp(event, name):
        """Delete preset from file"""
        if (event.shift)or(uu_ly.ProcConfirmAlert(name, limit=10.0)):
            prefs = Prefs()
            ProcPresetFile(prefs, "Remove", name=name)
            ProcPresetFile(prefs, "Load")
    def AddPresetOp(context, event, name):
        """Add preset to a tree"""
        prefs = Prefs()
        if event.shift:
            prefs.nameOfPresetToExport = name
            return {'CANCELLED'}
        dict_preset = NtpData.dict_presets[name]['eval']
        bpy.ops.node.select_all(action='DESELECT')
        tree = context.space_data.edit_tree
        list_nodes = AddPresetToTree(tree, dict_preset)
        assert list_nodes
        tree.nodes.active = list_nodes[-1]
        bpy.ops.node.translate_attach('INVOKE_DEFAULT')
        key = NtpData.GetKeyForDictWo(context)
        if (prefs.isPanelHideHeader)and(NtpData.dict_whereOpened[key]==1):
            NtpData.dict_whereOpened[key] = 0

class PanelNodeTextPresets(bpy.types.Panel):
    bl_idname = 'NTP_PT_NodeTextPresets'
    bl_label = "Node Text Presets"
    bl_space_type = 'NODE_EDITOR'
    @classmethod
    def poll(cls, context):
        return not not context.space_data.edit_tree
    def draw(self, context):
        colLy = self.layout.column()
        colRoot = colLy.column(align=True)
        prefs = Prefs()
        tree = context.space_data.edit_tree
        aNd = tree.nodes.active
        if prefs.isPanelHideHeader:
            rowHeader = colRoot.row(align=True)
            isOpened = NtpData.dict_whereOpened.get(NtpData.GetKeyForDictWo(context), False)
            rowHeader.operator(OpSimpleExec.bl_idname, text=PanelNodeTextPresets.bl_label, icon='DOWNARROW_HLT' if isOpened else 'RIGHTARROW').exc = "NtpOp.TogglePanelOp(context)"
            ##
            if not isOpened:
                return
            rowHeader.operator(OpSimpleExec.bl_idname, text="", icon='PINNED' if isOpened==2 else 'UNPINNED').exc = "NtpOp.TogglePinOp(context)"
            #rowCopy = rowHeader.row(align=True) #P.s. кнопка копирования изначально была здесь.
            colPanel = colRoot.box().column()
        else:
            colPanel = colRoot.column()
        intAllowFilter = prefs.intAllowFilter
        if intAllowFilter:
            rowSearch = colPanel.row(align=True)
            rowFilter = rowSearch.row(align=True)
            txt_filter = rowFilter.prop_and_get(prefs,'filter', text="", icon='SORTBYEXT')
            rowSearch.active = (prefs.intAllowFilter==1)or(not not txt_filter)
        ##
        colList = colPanel.column(align=True)
        if NtpData.txtErrorInLoad:
            colList.alert = True
            colList.label(text=NtpData.txtErrorInLoad)
            return
        else:
            patr = re.compile(txt_filter) if (intAllowFilter)and(txt_filter) else None #Заметка: аккуратнее с txt_filter, см. объявление.
            sco = 0
            for dk, dv in NtpData.dict_presets.items():
                if (not patr)or(re.search(patr, dk)):
                    if dv['eval']['tree']==context.space_data.tree_type:
                        rowItem = colList.row(align=True)
                        rowItem.operator(OpSimpleExec.bl_idname, text=dk, icon='IMPORT').exc = f"NtpOp.AddPresetOp(context, event, {repr(dk)})"
                        rowItem.operator(OpSimpleExec.bl_idname, text="", icon='TRASH' if uu_ly.ProcConfirmAlert(dk) else 'REMOVE').exc = f"NtpOp.DelPresetOp(event, {repr(dk)})" #REMOVE  X
                        sco += 1
            if intAllowFilter:
                rowFound = rowSearch.row(align=True)
                rowFound.alignment = 'CENTER'
                rowFound.label(text=" "+str(sco))
        ##
        intAllowExport = prefs.intAllowExport
        if intAllowExport==2:
            rowFolder = colPanel.row(align=True)
            rowFolder.prop(prefs,'pathToPresetFile', text="")
            rowFolder.operator(OpSimpleExec.bl_idname, text="", icon='RESTRICT_VIEW_OFF').exc = "NtpOp.OpenFolderOp()" #RESTRICT_VIEW_OFF  FOLDER_REDIRECT
            rowFolder.operator(OpSimpleExec.bl_idname, text="", icon='FILE_REFRESH').exc = "NtpOp.ReloadOp()"
        if intAllowExport:
            colIo = colPanel.column(align=True)
            rowIo = colIo.row(align=True)
            tgl = not not (aNd)and(aNd.select)
            rowIo.active = tgl
            if True:
                uu_ly.LyNiceColorProp(rowIo, prefs,'nameOfPresetToExport', text="Name:")
            else:
                rowIo.prop(prefs,'nameOfPresetToExport', text="Name")
            rowEx = rowIo.row(align=True)
            rowOp = rowEx.row(align=True)
            rowOp.alignment = 'CENTER'
            rowOp.operator(OpSimpleExec.bl_idname, text="Export", icon='EXPORT').exc = "NtpOp.ExportOp(context)"
            rowOp.enabled = (tgl)and(not not prefs.nameOfPresetToExport)
            rowEx.operator(OpSimpleExec.bl_idname, text="", icon='COPYDOWN').exc = "NtpOp.CopyDiffOp(context, event)" #SELECT_DIFFERENCE  DUPLICATE  MOD_BOOLEAN  SELECT_INTERSECT

def Prefs():
    return bpy.context.preferences.addons[bl_info['name']].preferences

def ReregUpdatePanel(self, context):
    PanelNodeTextPresets.bl_category = self.txtPanelCategory
    PanelNodeTextPresets.bl_region_type = 'UI' if PanelNodeTextPresets.bl_category else 'TOOLS'
    PanelNodeTextPresets.bl_options = {'HIDE_HEADER'} if self.isPanelHideHeader else set()
    if panel:=getattr(bpy.types, PanelNodeTextPresets.bl_idname, None):
        bpy.utils.unregister_class(panel)
    bpy.utils.register_class(PanelNodeTextPresets)
def UpdateAllowFilter(self, context):
    if not self.intAllowFilter:
        self.filter = ""
class AddonPrefs(bpy.types.AddonPreferences):
    bl_idname = bl_info['name'] if __name__=="__main__" else __name__
    filter: bpy.props.StringProperty(name="Filter", default="(?i).*")
    pathToPresetFile:     bpy.props.StringProperty(name="Path to file with presets", default=os.path.join(os.environ['USERPROFILE'], "Desktop")+"\\ntp_presets.txt", subtype='FILE_PATH', update=UpdatePathToPresetFile)
    nameOfPresetToExport: bpy.props.StringProperty(name="Name of preset to export", default="")
    intAllowFilter: bpy.props.IntProperty(name="Show search", default=2, min=0, max=2, update=UpdateAllowFilter)
    intAllowExport: bpy.props.IntProperty(name="Show export", default=2, min=0, max=2, update=UpdateAllowFilter)
    txtPanelCategory: bpy.props.StringProperty(name="Meta Panel Category", default="", update=ReregUpdatePanel)
    isPanelHideHeader: bpy.props.BoolProperty(name="Meta Panel Hide Header", default=True, update=ReregUpdatePanel)
    def DrawTabSettings(self, context, where):
        colMain = uu_ly.LyAddHeaderedBox(where, "preferences", active=False).column()
        uu_ly.LyNiceColorProp(colMain, self,'pathToPresetFile')
        colMain.prop(self,'intAllowFilter')
        colMain.prop(self,'intAllowExport')
        uu_ly.LyNiceColorProp(colMain, self,'txtPanelCategory')
        colMain.prop(self,'isPanelHideHeader')
    def draw(self, context):
        colMain = self.layout.column()
        self.DrawTabSettings(context, colMain)

def register():
    bpy.utils.register_class(OpSimpleExec)
    bpy.utils.register_class(AddonPrefs)
    prefs = Prefs()
    prefs.nameOfPresetToExport = ""
    prefs.filter = ""
    ReregUpdatePanel(prefs, None)
def unregister():
    bpy.utils.unregister_class(AddonPrefs)
    bpy.utils.unregister_class(OpSimpleExec)

if __name__=="__main__":
    register()
