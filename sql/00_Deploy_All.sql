-- ============================================================================
-- Master deploy for PumpConfiguratorDB (sqlcmd :r include list).
-- Run with SQLCMD mode enabled.
--
-- Ordering is dependency-driven. Filenames are spelled in full because several
-- numeric prefixes collide (two 18_, 19_, 20_, 21_, 23_ files exist for
-- different subsystems) - always reference by full name, not number.
--
-- NOT included here (run manually / as needed): one-off data migrations, import
-- staging loads, and verify scripts:
--   05_Seed_Development_Data, 06_Test_Suite (dev/test only),
--   10A/11A (segment import validate), 18_Add_Pricing_Source_Series_Lineage,
--   19_Verify_M021_Pricing_Publication, 20_Add_Generic_Pricing_Conditions,
--   21_Verify_M022_Combined_Pricing_Publication.
-- Runtime data (constraints, motor constraints, combine vars, item
-- applicability, series field options, attributes) is loaded by the Python
-- loaders in scripts/ against the active publication, not by this deploy.
-- ============================================================================

-- Core database + schema
:r .\01_Create_Database.sql
:r .\02_Create_Core_Tables.sql
:r .\03_Create_Procedures.sql
:r .\04_Create_Views.sql

-- Compiler / staging + identifier engine metadata
:r .\07_Create_Compiler_Staging.sql
:r .\08_Create_Option_Constraint_Staging.sql
:r .\09_Create_Identifier_Engine_Metadata.sql

-- Segment combination metadata (lookup tables + index fix)
:r .\10_Create_Segment_Combination_Metadata.sql
:r .\10A_Fix_Segment_Combination_Index.sql
:r .\11_Create_Segment_Combination_Import_Staging.sql

-- Publication + attribute metadata (AttributeValue underpins fn_LookupIdentifierCode)
:r .\12_Create_Metadata_Publication_And_Attributes.sql
:r .\13_Create_Attribute_Publication_Procedures.sql
:r .\14_Create_Series_Field_Option_Metadata.sql
:r .\15_Create_Field_Option_Dependency_Metadata.sql

-- Configured-product registry (child tables; persistence proc)
:r .\16_Create_Configured_Product_Registry.sql

-- Pricing publication
:r .\17_Create_Pricing_Publication.sql

-- Constraint metadata (feasible/motor/combine/item + field map)
:r .\18_Create_Motor_Constraint.sql
:r .\19_Create_Combine_Variables.sql
:r .\20_Create_Item_Applicability.sql
:r .\21_Create_Constraint_Field_Map.sql

-- IDENTIFIER AUTHORITY (F150): fn_LookupIdentifierCode, usp_GeneratePartNumber,
-- usp_GenerateSKU, usp_ResolveConfiguredProduct, then the Option-B authoritative
-- assembler which depends on usp_GenerateSKU + usp_GetOrCreateConfiguredProduct.
:r .\22_Create_Identifier_Generation.sql
:r .\23_Create_Assemble_Configured_Product.sql

-- BOM + Quote engines (U130/U140)
:r .\23_Create_BOM_Engine.sql
:r .\24_Create_Quote_Engine.sql
