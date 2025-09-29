

interface InfoItem {
  key: string;
  value: string;
}

interface InfoDisplayProps {
  items: InfoItem[];
  className?: string;
}

export const InfoDisplay = ({ items, className = "" }: InfoDisplayProps) => (
  <div className={`text-sm text-muted-foreground space-y-1 ${className}`}>
    {items.map(({ key, value }) => (
      <div key={key}>
        <span className="font-medium">{key}:</span> {value}
      </div>
    ))}
  </div>
);

export type { InfoItem };