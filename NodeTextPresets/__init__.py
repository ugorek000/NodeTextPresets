bl_info = {'name':"NodeTextPresets", 'author':"ugorek",
           'version':(2,0,0), 'blender':(4,1,0), 'created':"2024.03.29",
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
import uu_regutils
rud = uu_regutils.ModuleData()

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
        dict_result["props"] = GetNdDifferenceAsText(ndTar, ndRef, "'{dk}':{val}", set_ignoredProps={'name', 'select', 'show_texture', 'is_active_output'})
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
        case "Load":
            #Заметка: в остальных действиях нет try, потому что они вызывают "Load".
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

isUpdatingPathToPresetFile = False
def UpdatePathToPresetFile(self, context):
    global isUpdatingPathToPresetFile
    if isUpdatingPathToPresetFile:
        return
    isUpdatingPathToPresetFile = True
    self.pathToPresetFile = self.pathToPresetFile.strip("\"")
    ProcPresetFile(self, "Load")
    isUpdatingPathToPresetFile = False

fitOptionItems = ( ('NONE',       "None",              "None"),
                   ('TOGGLE',     "Toggle Visibility", "Toggle visibility of Panel"),
                   ('COPYDIFF',   "Copy Difference",   "Copy selected nodes as raw preset"),
                   ('EXPORT',     "Export",            "Export with overwriting"),
                   ('ADD',        "Add",               "Add"),
                   ('DEL',        "Del",               "Delete"),
                   ('RELOAD',     "Reload",            "Reload from file"),
                   ('OPENFOLDER', "Open Folder",       "Open folder of presets file") )
class OpNodeTextPresets(bpy.types.Operator):
    bl_idname = 'node.text_presets'
    bl_label = "Node Presets"
    bl_options = {'UNDO'}
    option: bpy.props.EnumProperty(name="Option", default='NONE', items=fitOptionItems)
    name: bpy.props.StringProperty(name="Name")
    def invoke(self, context, event):
        tree = context.space_data.edit_tree
        prefs = Prefs()
        match self.option:
            case 'TOGGLE':
                key = NtpData.GetKeyForDictWo(context)
                NtpData.dict_whereOpened.setdefault(key, False)
                NtpData.dict_whereOpened[key] = not NtpData.dict_whereOpened[key]
                if NtpData.dict_whereOpened[key]:
                    ProcPresetFile(prefs, "Load")
            case 'COPYDIFF':
                aNd = tree.nodes.active
                if (aNd)and(aNd.select):
                    text = GetTextPresetFromTree(tree)
                    if event.shift:
                        text =  f"\"{prefs.nameOfPresetToExport}\":\""+txt.replace("\"","\\\"")+"]}\","
                    context.window_manager.clipboard = text
            case 'OPENFOLDER':
                #subprocess.Popen(f"explorer /select,\"{prefs.pathToPresetFile}\"")
                os.startfile(os.path.dirname(prefs.pathToPresetFile))
            case 'RELOAD':
                ProcPresetFile(prefs, "Load")
            case 'EXPORT':
                aNd = tree.nodes.active
                if (aNd)and(aNd.select)and(name:=prefs.nameOfPresetToExport):
                    ProcPresetFile(prefs, "Append", name=name, data=GetTextPresetFromTree(tree))
                    prefs.nameOfPresetToExport = ""
                    ProcPresetFile(prefs, "Load")
            case 'DEL':
                if (UserAlertDel.sure)and(UserAlertDel.name==self.name):
                    ProcPresetFile(prefs, "Remove", name=self.name)
                    ProcPresetFile(prefs, "Load")
                    UserAlertDel.sure = False
                else:
                    UserAlertDel.sure = True
                    UserAlertDel.name = self.name
                    UserAlertDel.time = int(time.perf_counter())
            case 'ADD':
                if event.shift:
                    prefs.nameOfPresetToExport = self.name
                    return {'CANCELLED'}
                dict_preset = NtpData.dict_presets[self.name]['eval']
                bpy.ops.node.select_all(action='DESELECT')
                list_nodes = AddPresetToTree(tree, dict_preset)
                assert list_nodes
                tree.nodes.active = list_nodes[-1]
                bpy.ops.node.translate_attach('INVOKE_DEFAULT')
                NtpData.dict_whereOpened[NtpData.GetKeyForDictWo(context)] = False
        return {'FINISHED'}

class UserAlertDel:
    sure = False
    name = ""
    time = 0.0
class PanelNodeTextPresets(bpy.types.Panel):
    bl_idname = 'NTP_PT_NodeTextPresets'
    bl_label = "Node Text Presets"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(cls, context):
        return not not context.space_data.edit_tree
    def draw(self, context):
        colLy = self.layout.column()
        colRoot = colLy.column(align=True)
        prefs = Prefs()
        tree = context.space_data.edit_tree
        aNd = tree.nodes.active
        active = not not (aNd)and(aNd.select)
        rowHeader = colRoot.row(align=True)
        isOpened = NtpData.dict_whereOpened.get(NtpData.GetKeyForDictWo(context), False)
        rowHeader.operator_props(OpNodeTextPresets.bl_idname, text=PanelNodeTextPresets.bl_label, icon='DOWNARROW_HLT' if isOpened else 'RIGHTARROW', option='TOGGLE')
        if isOpened:
            #rowCopy = rowHeader.row(align=True) #P.s. кнопка копирования изначально была здесь.
            colPanel = colRoot.box().column()
            rowFolder = colPanel.row(align=True)
            rowFolder.prop(prefs,'pathToPresetFile', text="")
            rowFolder.operator_props(OpNodeTextPresets.bl_idname, text="", icon='RESTRICT_VIEW_OFF', option='OPENFOLDER') #RESTRICT_VIEW_OFF  FOLDER_REDIRECT
            rowFolder.operator_props(OpNodeTextPresets.bl_idname, text="", icon='FILE_REFRESH', option='RELOAD')
            ##
            colList = colPanel.column(align=True)
            if NtpData.txtErrorInLoad:
                colList.alert = True
                colList.label(text=NtpData.txtErrorInLoad)
                return
            else:
                if UserAlertDel.sure:
                    secs = 10-(time.perf_counter()-UserAlertDel.time)
                    if secs<0:
                        UserAlertDel.sure = False
                #todo кажется ещё нужен поисковой фильтр.
                for dk, dv in NtpData.dict_presets.items():
                    if dv['eval']['tree']==context.space_data.tree_type:
                        rowItem = colList.row(align=True)
                        rowItem.operator_props(OpNodeTextPresets.bl_idname, text=dk, icon='IMPORT', option='ADD', name=dk)
                        rowItem.operator_props(OpNodeTextPresets.bl_idname, text="", icon='TRASH' if (UserAlertDel.sure)and(UserAlertDel.name==dk) else 'REMOVE', option='DEL', name=dk) #REMOVE  X
            ##
            colIo = colPanel.column(align=True)
            rowIo = colIo.row(align=True)
            rowIo.active = active
            if True:
                uu_ly.LyNiceColorProp(rowIo, prefs,'nameOfPresetToExport', text="Name:")
            else:
                rowIo.prop(prefs,'nameOfPresetToExport', text="")
            rowEx = rowIo.row(align=True)
            rowOp = rowEx.row(align=True)
            rowOp.alignment = 'CENTER'
            rowOp.operator_props(OpNodeTextPresets.bl_idname, text="Export", icon='EXPORT', option='EXPORT')
            rowOp.enabled = (active)and(not not prefs.nameOfPresetToExport)
            rowEx.operator_props(OpNodeTextPresets.bl_idname, text="", icon='COPYDOWN', option='COPYDIFF') #SELECT_DIFFERENCE  DUPLICATE  MOD_BOOLEAN  SELECT_INTERSECT

def Prefs():
    return bpy.context.preferences.addons[bl_info['name']].preferences

class AddonPrefs(bpy.types.AddonPreferences):
    bl_idname = bl_info['name'] if __name__=="__main__" else __name__
    pathToPresetFile:     bpy.props.StringProperty(name="Path to file with presets", default=os.path.join(os.environ['USERPROFILE'], "Desktop")+"\\ntp_presets.txt", subtype='FILE_PATH', update=UpdatePathToPresetFile)
    nameOfPresetToExport: bpy.props.StringProperty(name="Name of preset to export", default="")
    def DrawTabSettings(self, context, where):
        uu_ly.LyNiceColorProp(uu_ly.LyAddHeaderedBox(where, "preferences", active=False).column(), self,'pathToPresetFile')
    def draw(self, context):
        colMain = self.layout.column()
        self.DrawTabSettings(context, colMain)

def register():
    uu_regutils.LazyRegAll(rud, globals())
    Prefs().nameOfPresetToExport = ""
def unregister():
    uu_regutils.UnregKmiDefs(rud)

if __name__=="__main__":
    register()
