-- สร้างตาราง training_sla สำหรับ Supabase
-- Schema: public
-- สามารถ TRUNCATE และ import ข้อมูลใหม่ได้

-- ลบตารางเดิม (ถ้ามี)
DROP TABLE IF EXISTS public.training_sla;

-- สร้างตารางใหม่
CREATE TABLE public.training_sla (
    -- Primary Key (auto-generated)
    row_id BIGSERIAL PRIMARY KEY,
    
    -- ข้อมูลช่าง
    no TEXT,
    first_name_th TEXT,
    last_name_th TEXT,
    full_name_th TEXT,
    first_name_en TEXT,
    last_name_en TEXT,
    depot_name TEXT,
    depot_code TEXT,
    province TEXT,
    national_id TEXT,
    birth_date_thai TEXT,
    age INTEGER,
    education TEXT,
    workgroup_status TEXT,
    
    -- ผลการอบรม
    theory_training_result TEXT,
    on_the_job_result TEXT,
    
    -- เอกสาร
    technician_profile_file TEXT,
    id_card_file TEXT,
    education_certificate_file TEXT,
    technician_photo_status TEXT,
    medical_certificate_file TEXT,
    pole_climbing_training TEXT,
    driver_license_file TEXT,
    criminal_record_document TEXT,
    background_check_status TEXT,
    payment_status TEXT,
    
    -- พื้นที่และรอบอบรม
    area TEXT,
    training_round_date TEXT,
    training_month TEXT,
    id TEXT,
    certificate TEXT,
    date_card TEXT,
    card TEXT,
    result TEXT,
    status TEXT,
    
    -- วันที่และ SLA รวม
    start_date TEXT,
    end_date TEXT,
    sla_total INTEGER,
    training_by TEXT,
    week TEXT,
    round_month TEXT,
    year TEXT,
    remark TEXT,
    model TEXT,
    update TEXT,
    status_group TEXT,
    
    -- รอบอบรม
    status_result_round TEXT,
    result_round TEXT,
    training_start TEXT,
    training_end TEXT,
    sla_training INTEGER,
    remark_training TEXT,
    
    -- OJT
    status_result_ojt TEXT,
    result_round_ojt TEXT,
    ojt_start TEXT,
    ojt_end TEXT,
    sla_ojt INTEGER,
    remark_ojt TEXT,
    
    -- เอกสาร (Document)
    status_doc TEXT,
    result_doc TEXT,
    doc_start TEXT,
    doc_end TEXT,
    sla_doc INTEGER,
    remark_doc TEXT,
    
    -- Genid/Card
    status_genid_card_card TEXT,
    result_genid_card_card TEXT,
    genid_card_start TEXT,
    genid_card_end TEXT,
    sla_genid_card INTEGER,
    remark_genid_card TEXT,
    
    -- Inspection
    status_inspection TEXT,
    result_inspection TEXT,
    inspection_start TEXT,
    inspection_end TEXT,
    sla_inspection INTEGER,
    remark_inspection TEXT,
    
    -- DFlow
    status_dflow TEXT,
    result_dflow TEXT,
    dflow_start TEXT,
    dflow_end TEXT,
    sla_dflow INTEGER,
    remark_dflow TEXT,
    
    -- Registration
    status_registration TEXT,
    result_registration TEXT,
    registration_start TEXT,
    registration_end TEXT,
    sla_registration INTEGER,
    remark_registration TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- สร้าง Index สำหรับการค้นหาที่ใช้บ่อย
CREATE INDEX idx_training_sla_province ON public.training_sla(province);
CREATE INDEX idx_training_sla_area ON public.training_sla(area);
CREATE INDEX idx_training_sla_status ON public.training_sla(status);
CREATE INDEX idx_training_sla_depot_code ON public.training_sla(depot_code);
CREATE INDEX idx_training_sla_full_name_th ON public.training_sla(full_name_th);

-- Enable Row Level Security (RLS)
ALTER TABLE public.training_sla ENABLE ROW LEVEL SECURITY;

-- ===================================
-- RLS Policies
-- ===================================

-- Policy: อนุญาตให้ทุกคนอ่านข้อมูลได้ (รวมถึง anon)
CREATE POLICY "Allow public read access" 
ON public.training_sla 
FOR SELECT 
TO anon, authenticated
USING (true);

-- Grant permissions (สำหรับ Supabase)
GRANT ALL ON public.training_sla TO postgres;
GRANT ALL ON public.training_sla TO anon;
GRANT ALL ON public.training_sla TO authenticated;
GRANT ALL ON public.training_sla TO service_role;

-- Comment
COMMENT ON TABLE public.training_sla IS 'ตารางเก็บข้อมูล SLA การฝึกอบรมช่าง';

-- ===================================
-- คำสั่งสำหรับลบข้อมูลและ Import ใหม่
-- ===================================

-- วิธีที่ 1: ลบข้อมูลทั้งหมด (เร็วกว่า DELETE)
-- TRUNCATE TABLE public.training_sla RESTART IDENTITY;

-- วิธีที่ 2: ลบข้อมูลทั้งหมดด้วย DELETE
-- DELETE FROM public.training_sla;

-- ===================================
-- ตัวอย่างการ Import ข้อมูลจาก CSV
-- ===================================

-- สำหรับ Supabase Dashboard:
-- 1. ไปที่ Table Editor > training_sla
-- 2. คลิก "Insert" > "Import data from CSV"
-- 3. เลือกไฟล์ CSV และ map columns

-- สำหรับ SQL (ต้องใช้ผ่าน psql หรือ connection ตรง):
-- COPY public.training_sla (no, first_name_th, last_name_th, ...) 
-- FROM '/path/to/file.csv' 
-- DELIMITER ',' 
-- CSV HEADER;
