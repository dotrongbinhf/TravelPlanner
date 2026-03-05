export function NumberStepper({
  value,
  min,
  max,
  onChange,
}: {
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly onChange: (v: number) => void;
}) {
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (raw === "") {
      onChange(min);
      return;
    }
    const num = parseInt(raw, 10);
    if (!isNaN(num)) {
      onChange(Math.max(min, Math.min(max, num)));
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        className="w-7 h-7 rounded-md border border-gray-200 flex items-center justify-center text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-30"
      >
        −
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={value}
        onChange={handleInputChange}
        className="w-10 h-7 text-center text-sm font-semibold text-gray-800 border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={value >= max}
        className="w-7 h-7 rounded-md border border-gray-200 flex items-center justify-center text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-30"
      >
        +
      </button>
    </div>
  );
}
