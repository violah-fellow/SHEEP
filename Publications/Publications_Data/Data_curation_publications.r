library(tidyverse)
library(readxl)

# Read in the search data (ALL entries)
## List with files
file_list <- c(
    list.files("Publications/Publications_Data/", pattern = "Search term*", full.names = TRUE),
    list.files("Publications/Publications_Data/", pattern = "Top 500*", full.names = TRUE)
)

## read xlsx files
all_list <- lapply(file_list, read_excel, skip = 1)

## bind them together, deduplicate by Publication ID and filter for research articles
all <- all_list %>%
    bind_rows() %>%
    distinct(`Publication ID`, .keep_all = TRUE) %>%
    dplyr::filter(`Publication Type` == "Article")

# Read in in scope data
in_scope <- read_excel("Publications/Publications_Data/IN SCOPE 2025.xlsx", skip = 1) %>%
    dplyr::filter(`Publication Type` == "Article")

# Read in labelled data
labelled <- read_excel("Publications/Publications_Data/Copy of Publications data 2026.xlsx")

## filter for in scope
labelled <- labelled %>%
    filter(`Publication ID` %in% in_scope$`Publication ID`)
## gives 1094 publications

## are all in scope publications captured in the search data?
summary(in_scope$`Publication ID` %in% all$`Publication ID`)
## No, one publication is not captured
## --> which one?
in_scope %>%
    filter(!(`Publication ID` %in% all$`Publication ID`))
## pub.1197164068: Food and ethics: How German far-right defend their dietary ideology in times of climate change
## Include or exclude? --> Ignore=exclude for now

# Create new column for in/out of scope
all <- all %>%
    mutate(scope = ifelse(`Publication ID` %in% in_scope$`Publication ID`, "in", "out"))

# Join with AP pillar and research category label from labelled data
all <- all %>%
    left_join(labelled %>% select(`Publication ID`, `Pillar`, `Research category`), by = "Publication ID")

# Filter for year = 2025 & available title and abstract & articles
all <- all %>%
    dplyr::filter(PubYear == 2025) %>% # 3876
    dplyr::filter(!is.na(Title) & !is.na(Abstract)) # 3869

# Rename some columns and select
all <- all %>%
    dplyr::rename(
        id = `Publication ID`,
        title = Title, abstract = Abstract,
        year = PubYear,
        pillar = Pillar, research_category = `Research category`
    ) %>%
    dplyr::select(id, title, abstract, year, scope, pillar, research_category)

# Repare/clean some research category labels
all <- all %>%
    mutate(research_category = str_remove(research_category, "\\ \\(incl Texturization methods\\)+")) %>%
    mutate(research_category = ifelse(
        research_category == "Consumer and market research", "Consumer & market research",
        ifelse(research_category == "Health /nutrition", "Health & nutrition",
            ifelse(research_category == "No sector assigned", "Other", research_category)
        )
    ))

# write csv
write_csv(all, "Publications/publications_curated.csv")

# Is the labelling balanced?

# AP pillar is somewhat balanced:
# 1 CC        98
# 2 CM        98
# 3 F        151
# 4 PB       695
# 5 NA      3773

# Research category is very unbalanced:
#  1 Bioprocess design             33
#  2 Cell culture media             9
#  3 Cell line development          8
#  4 Consumer & market research   129
#  5 Crop development              37
#  6 End product formulation      148
#  7 Feedstocks                    29
#  8 Food safety & quality         45
#  9 Health & nutrition            63
# 10 Impact assessments            34
# 11 Ingredient optimisation      344
# 12 Other                         53
# 13 Scaffolding                   14
# 14 Strain development            27
# 15 Target molecule selection      4
# 16 Texturization methods         65

# And by pillar
# PB
#  1 Consumer & market research    64
#  2 Crop development              37
#  3 End product formulation      134
#  4 Food safety & quality         33
#  5 Health & nutrition            46
#  6 Impact assessments            18
#  7 Ingredient optimisation      283
#  8 Other                         11
#  9 Strain development            11
# 10 Texturization methods         58

# F
#  1 Bioprocess design             23
#  2 Consumer & market research     1
#  3 End product formulation        5
#  4 Feedstocks                    29
#  5 Food safety & quality          2
#  6 Health & nutrition            10
#  7 Impact assessments             6
#  8 Ingredient optimisation       44
#  9 Other                         10
# 10 Strain development            16
# 11 Target molecule selection      4
# 12 Texturization methods          1

# CM
#  1 Bioprocess design              9
#  2 Cell culture media             9
#  3 Cell line development          8
#  4 Consumer & market research    32
#  5 End product formulation        2
#  6 Food safety & quality          3
#  7 Impact assessments             5
#  8 Other                         13
#  9 Scaffolding                   14
# 10 Texturization methods          3

# CC
# 1 Bioprocess design              1
# 2 Consumer & market research    32
# 3 End product formulation        7
# 4 Food safety & quality          7
# 5 Health & nutrition             7
# 6 Impact assessments             5
# 7 Ingredient optimisation       17
# 8 Other                         19
# 9 Texturization methods          3
