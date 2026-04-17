import { ScrollArea } from "@/components/ui/scroll-area";

import { ListingCard, type ListingCardProps } from "./ListingCard";

export function ListingCarousel({
  items,
}: {
  items: ListingCardProps[];
}) {
  return (
    <ScrollArea className="overflow-x-auto">
      <div className="flex gap-4 pb-2">
        {items.map((item) => (
          <ListingCard compact key={item.id} {...item} />
        ))}
      </div>
    </ScrollArea>
  );
}
