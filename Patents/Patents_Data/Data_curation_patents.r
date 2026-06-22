library(tidyverse)
library(readxl)

# Read in the search data (ALL entries)
## List with files
file_list <- list.files("Patents/Patents_Data/", pattern = "Search term*", full.names = TRUE)

## read xlsx files
all_list <- lapply(file_list, read_excel, skip = 1)

## bind them together, deduplicate by Publication ID and filter for research articles
all <- all_list %>%
    bind_rows() %>%
    arrange(by = `Family ID`, desc(`Publication date`)) %>%
    distinct(`Publication number`, .keep_all = TRUE) %>%
    mutate(id = str_remove(`Dimensions URL`, "https://app.dimensions.ai/details/patent/"))

# Read in in scope data
in_scope <- read_excel("Patents/Patents_Data/IN SCOPE 2025.xlsx", skip = 1) %>%
    mutate(id = str_remove(`Dimensions URL`, "https://app.dimensions.ai/details/patent/"))

# Read in labelled data
labelled <- read_excel("Patents/Patents_Data/Copy of Patents data 2026.xlsx", sheet = "ALL patents 2015-2025") %>%
    dplyr::filter(`Publication year` == 2025) %>%
    mutate(id = str_remove(`Dimensions URL`, "https://app.dimensions.ai/details/patent/"))

## filter for in scope
labelled <- labelled %>%
    filter(`Publication number` %in% in_scope$`Publication number`)
## gives 1567 patents

## are all in scope patents captured in the search data?
summary(in_scope$`Publication number` %in% all$`Publication number`)
summary(in_scope$`Family ID` %in% all$`Family ID`)

summary(labelled$id %in% all$id)
##
in_scope %>%
    filter(!(`Publication number` %in% all$`Publication number`))

# Create new column for in/out of scope
labelled  <- labelled %>%
    mutate(scope = "in")

# Join with AP pillar, research category and other labels from labelled data
all <- all %>%
    left_join(labelled %>% 
    dplyr::select(`Publication number`, `Application number`, `Family ID`, scope, 
                  `Pillar`, `Category`, `End product`, `Ingredient`, `BF/PF`), 
    by = c("Publication number", "Application number", "Family ID")) %>%
    mutate(scope = replace_na(scope, "out"))

# Filter for available title and abstract & articles
all <- all %>%
    dplyr::filter(!is.na(`Patent title`) & !is.na(Abstract)) 

# overview in vs out of scope
all %>% 
    group_by(scope) %>%
    summarise(n=n())

# Rename some columns and select
all <- all %>%
    dplyr::rename(
        publication_number = `Publication number`,
        application_number = `Application number`,
        family_id = `Family ID`,
        title = `Patent title`, abstract = Abstract,
        granted_date = `Granted date`, granted_year = `Granted year`,
        publication_date = `Publication date`, publication_year = `Publication year`, 
        filing_date = `Filed date`, filing_status = Status, year = `Filed year`,
        priority_date = `Priority date`, priority_year = `Priority year`,
        cpc = CPC, jurisdiction = Jurisdiction,
        pillar = Pillar, research_category = Category,
        endproduct = `End product`, ingredient = Ingredient, subpillar = `BF/PF`
    )

# Overview
all %>% group_by(pillar) %>% summarise(n=n())
all %>% group_by(research_category) %>% summarise(n=n())
all %>% group_by(endproduct) %>% summarise(n=n())
all %>% group_by(ingredient) %>% summarise(n=n())

# Correct some of the columns
all <- all %>%
    mutate(endproduct = gsub("N/A", NA, endproduct))

# write csv
write_csv(all, "Patents/Patents_Data/patents_curated.csv")

# Is the labelling balanced?

# AP pillar is somewhat balanced:
# 1 CC       106
# 2 CM       183
# 3 F        178
# 4 PB       765
# 5 NA      1097

# Research category is very unbalanced:
#  1 Bioprocess design           110
#  2 Cell culture media           20
#  3 Cell line development        41
#  4 Crop development              2
#  5 End product formulation     422
#  6 Ingredient optimisation     428
#  7 Scaffolding                  30
#  8 Strain development           35
#  9 Target molecule selection    28
# 10 Texturization methods       116
# 11 NA                         1097

# End product
#  1 Cheese                                    69
#  2 Chocolate, desserts, and confectionery    18
#  3 Cream and ice cream                       18
#  4 Cross-cutting                            302
#  5 Eggs and egg proteins                     27
#  6 Fish and seafood                          12
#  7 Meat                                     524
#  8 Milk and milk proteins                   222
#  9 Spreads, sauces, and condiments            4
# 10 Yoghurt and fermented dairy               32
# 11 NA                                      1101

# Ingredient
# 1 Colours                              17
# 2 Emulsions, gels, and binders         93
# 3 Fats and oils                        44
# 4 Flavours and aromas                  72
# 5 Isolates, concentates, and flours   110
# 6 NA                                 1993