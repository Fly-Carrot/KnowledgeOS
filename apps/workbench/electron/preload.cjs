const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("knowledgeosWorkbench", {
  isElectron: true,
  getWorkspaces: () => ipcRenderer.invoke("workbench:workspaces"),
  addWorkspace: () => ipcRenderer.invoke("workbench:add-workspace"),
  removeWorkspace: (id) => ipcRenderer.invoke("workbench:remove-workspace", id),
  selectWorkspace: (id) => ipcRenderer.invoke("workbench:select-workspace", id),
  runDoctor: (id) => ipcRenderer.invoke("workbench:run-doctor", id)
});
