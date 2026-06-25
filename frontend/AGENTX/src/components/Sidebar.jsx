const files = [
  "main.py",
  "auth.py",
  "database.py",
  "utils.py",
  "config.py",
];

function Sidebar() {
  return (
    <div className="bg-slate-800 rounded-xl p-4 h-[500px]">

      <h2 className="text-xl font-bold mb-4">
         Repository
      </h2>

      {files.map((file) => (
        <div
          key={file}
          className="p-2 rounded hover:bg-slate-700 cursor-pointer transition"
        >
           {file}
        </div>
      ))}

    </div>
  );
}

export default Sidebar;