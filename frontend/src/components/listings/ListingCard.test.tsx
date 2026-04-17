import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ListingCard } from "./ListingCard";

describe("ListingCard", () => {
  it.each([
    {
      title: "Madrid Central Apartment",
      city: "Madrid",
      price: 450000,
      dealScore: 93,
      expectedPrice: "€450,000",
      expectedBadge: "dealScore: 93",
    },
    {
      title: "Porto Riverside Loft",
      city: "Porto",
      price: 275000,
      dealScore: 81,
      expectedPrice: "€275,000",
      expectedBadge: "dealScore: 81",
    },
  ])("renders price, location, and deal score for $title", (testCase) => {
    render(
      <ListingCard
        area={82}
        bedrooms={3}
        city={testCase.city}
        dealScore={testCase.dealScore}
        id="listing-1"
        price={testCase.price}
        title={testCase.title}
      />,
    );

    expect(screen.getByText(testCase.title)).toBeInTheDocument();
    expect(screen.getByText(testCase.city)).toBeInTheDocument();
    expect(screen.getByText(testCase.expectedPrice)).toBeInTheDocument();
    expect(screen.getByText(testCase.expectedBadge)).toBeInTheDocument();
  });
});
