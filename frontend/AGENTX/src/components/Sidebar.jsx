function Sidebar({ files, selectedFile, onSelectFile }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 h-[500px] overflow-y-auto">

      <h2 className="text-xl font-bold mb-4">
         Repository
      </h2>

      {files.length === 0 && (
        <p className="text-sm text-slate-400">No files yet — run an analysis.</p>
      )}

      {files.map((file) => (
        <div
          key={file}
          onClick={() => onSelectFile(file)}
          className={`p-2 rounded cursor-pointer transition ${
            file === selectedFile ? "bg-cyan-600" : "hover:bg-slate-700"
          }`}
        >
           {file}
        </div>
      ))}

    </div>
  );
}

export default Sidebar;
