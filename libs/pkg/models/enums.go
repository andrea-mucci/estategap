package models

type PropertyCategory string

const (
	PropertyCategoryResidential PropertyCategory = "residential"
	PropertyCategoryCommercial  PropertyCategory = "commercial"
	PropertyCategoryIndustrial  PropertyCategory = "industrial"
	PropertyCategoryLand        PropertyCategory = "land"
)

type ListingStatus string

const (
	ListingStatusActive   ListingStatus = "active"
	ListingStatusDelisted ListingStatus = "delisted"
	ListingStatusSold     ListingStatus = "sold"
)

type SubscriptionTier string

const (
	SubscriptionTierFree   SubscriptionTier = "free"
	SubscriptionTierBasic  SubscriptionTier = "basic"
	SubscriptionTierPro    SubscriptionTier = "pro"
	SubscriptionTierGlobal SubscriptionTier = "global"
	SubscriptionTierAPI    SubscriptionTier = "api"
)

type DealTier int16

const (
	DealTierGreatDeal  DealTier = 1
	DealTierGoodDeal   DealTier = 2
	DealTierFair       DealTier = 3
	DealTierOverpriced DealTier = 4
)
