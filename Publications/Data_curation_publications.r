library(tidyverse)
library(readxl)

# Read in the search data (ALL entries)
## List with files
file_list <- c(
    list.files("Publications_Data/", pattern = "Search term*", full.names = TRUE),
    list.files("Publications_Data/", pattern = "Top 500*", full.names = TRUE)
)

## read xlsx files
all_list <- lapply(file_list, read_excel, skip = 1)

## bind them together, deduplicate by Publication ID and filter for research articles
all <- all_list %>%
    bind_rows() %>%
    distinct(`Publication ID`, .keep_all = TRUE) %>%
    dplyr::filter(`Document Type` == "Research Article")

# Read in in scope data
in_scope <- read_excel("Publications_Data/IN SCOPE 2025.xlsx", skip = 1)

# Read in labelled data
labelled <- read_excel("Publications_Data/Copy of Publications data 2026.xlsx")

## filter for in scope
labelled %>%
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

# write csv
write_csv(all, "Publications_Data/publications_curated.csv")

# Is the labelling balanced?

# AP pillar is somewhat balanced:
# 1 CC       109
# 2 CM       113
# 3 F        165
# 4 PB       716
# 5 NA      4148

# Research category is very unbalanced:
#  1 Bioprocess design                              35
#  2 Cell culture media                             10
#  3 Cell line development                           9
#  4 Consumer & market research                    134
#  5 Consumer and market research                    1
#  6 Crop development                               37
#  7 End product formulation                       154
#  8 Feedstocks                                     30
#  9 Food safety & quality                          48
# 10 Health & nutrition                             60
# 11 Health /nutrition                               4
# 12 Impact assessments                             39
# 13 Ingredient optimisation                       357
# 14 Manufacturing (incl Texturization methods)      2
# 15 No sector assigned                              2
# 16 Other                                          67
# 17 Scaffolding                                    15
# 18 Strain development                             29
# 19 Target molecule selection                       5
# 20 Texturization methods                          64
# 21 NA                                           4149

# And by pillar
# PB
#  1 Consumer & market research                     65
#  2 Crop development                               37
#  3 End product formulation                       138
#  4 Food safety & quality                          33
#  5 Health & nutrition                             42
#  6 Health /nutrition                               4
#  7 Impact assessments                             19
#  8 Ingredient optimisation                       293
#  9 Manufacturing (incl Texturization methods)      1
# 10 No sector assigned                              1
# 11 Other                                          13
# 12 Strain development                             12
# 13 Texturization methods                          58

# F
#  1 Bioprocess design             24
#  2 Consumer & market research     2
#  3 End product formulation        5
#  4 Feedstocks                    30
#  5 Food safety & quality          4
#  6 Health & nutrition            10
#  7 Impact assessments             6
#  8 Ingredient optimisation       46
#  9 No sector assigned             1
# 10 Other                         14
# 11 Strain development            17
# 12 Target molecule selection      5
# 13 Texturization methods          1

# CM
# 1 Bioprocess design             10
#  2 Cell culture media            10
#  3 Cell line development          9
#  4 Consumer & market research    33
#  5 End product formulation        3
#  6 Food safety & quality          4
#  7 Impact assessments             8
#  8 Other                         17
#  9 Scaffolding                   15
# 10 Texturization methods          3
# 11 NA                             1

# CC
#  1 Bioprocess design                               1
#  2 Consumer & market research                     34
#  3 Consumer and market research                    1
#  4 End product formulation                         8
#  5 Food safety & quality                           7
#  6 Health & nutrition                              8
#  7 Impact assessments                              6
#  8 Ingredient optimisation                        18
#  9 Manufacturing (incl Texturization methods)      1
# 10 Other                                          23
# 11 Texturization methods                           2
