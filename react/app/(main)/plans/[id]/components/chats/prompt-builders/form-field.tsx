export function FormField({
  label,
  required,
  icon,
  children,
}: {
  readonly label: string;
  readonly required?: boolean;
  readonly icon?: React.ReactNode;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5 w-full">
      <label className="flex items-center gap-1.5 text-xs font-medium text-gray-700">
        {icon && <span className="text-blue-400">{icon}</span>}
        {label}
        {required && <span className="text-red-400">*</span>}
      </label>
      {children}
    </div>
  );
}
