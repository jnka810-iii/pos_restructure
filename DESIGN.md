---
version: alpha
name: Thai-Gov-Form-System
description: "A Thai-language design system for government data-entry applications, merged from the SAP and IBM Carbon analyses on getdesign.md. SAP supplies the look — a white working surface on a light-grey page, one acting blue, 8px control corners, a slate text ladder and zero letter-spacing. IBM Carbon supplies the form machinery — field states, a full semantic palette for validation; the fields themselves keep this system's original white boxes with a soft border and a blue focus halo, a full semantic palette for validation, a 4px spacing grid and 48px touch targets. Typography is rebuilt for Thai: Noto Sans Thai Variable, no tracking, line-height never below 1.4, and nothing smaller than 14px for running text. A solid deep-blue header keeps the page recognisably governmental."

colors:
  primary: "#0057d2"
  primary-hover: "#0040b0"
  primary-pressed: "#022879"
  on-primary: "#ffffff"
  header: "#0040b0"
  on-header: "#ffffff"
  on-header-muted: "#c9dcff"
  page: "#f5f6f7"
  canvas: "#ffffff"
  band: "#eaecee"
  band-blue: "#ebf8ff"
  field: "#f5f6f7"
  field-hover: "#eaecee"
  field-disabled: "#eaecee"
  ink: "#0b1d33"
  ink-heading-on-band: "#022879"
  ink-body: "#223548"
  ink-label: "#354a5f"
  ink-meta: "#475e75"
  ink-nav: "#545454"
  ink-disabled: "#8c8c8c"
  hairline: "#d5dadd"
  border-strong: "#8d8d8d"
  focus: "#0057d2"
  success: "#198038"
  success-bg: "#defbe6"
  warning: "#8e6a00"
  warning-fill: "#f1c21b"
  warning-bg: "#fcf4d6"
  error: "#da1e28"
  error-bg: "#fff1f1"
  info: "#0057d2"
  info-bg: "#ebf8ff"
  add-row: "#198754"
  add-row-end: "#20c997"
  add-row-hover: "#145c38"
  field-border: "#d0d8e3"

typography:
  page-title:
    fontFamily: Noto Sans Thai
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  header-title:
    fontFamily: Noto Sans Thai
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  section-title:
    fontFamily: Noto Sans Thai
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  subhead:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  body:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: 0
  body-sm:
    fontFamily: Noto Sans Thai
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  list-item:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 350
    lineHeight: 1.6
    letterSpacing: 0
  label:
    fontFamily: Noto Sans Thai
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  input:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  helper:
    fontFamily: Noto Sans Thai
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  button:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0
  tab:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  tab-active:
    fontFamily: Noto Sans Thai
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  table-header:
    fontFamily: Noto Sans Thai
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  table-cell:
    fontFamily: Noto Sans Thai
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  caption:
    fontFamily: Noto Sans Thai
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  badge:
    fontFamily: Noto Sans Thai
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  none: 0px
  sm: 4px
  md: 8px
  lg: 12px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 64px

components:
  gov-header:
    backgroundColor: "{colors.header}"
    textColor: "{colors.on-header}"
    typography: "{typography.header-title}"
    rounded: "{rounded.none}"
    height: 64px
    padding: 0 24px
  header-subtitle:
    backgroundColor: "{colors.header}"
    textColor: "{colors.on-header-muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
  header-status-chip:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: 4px 12px
  tab-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-nav}"
    typography: "{typography.tab}"
    rounded: "{rounded.none}"
    height: 48px
  tab:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-nav}"
    typography: "{typography.tab}"
    rounded: "{rounded.none}"
    padding: 12px 16px
    height: 48px
  tab-active:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    typography: "{typography.tab-active}"
    rounded: "{rounded.none}"
    padding: 12px 16px
    height: 48px
  count-badge:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 0 8px
    height: 20px
  form-section:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 24px
  section-header:
    backgroundColor: "{colors.band-blue}"
    textColor: "{colors.ink-heading-on-band}"
    typography: "{typography.section-title}"
    rounded: "{rounded.md}"
    padding: 12px 24px
    height: 52px
  section-header-solid:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.section-title}"
    rounded: "{rounded.md}"
    padding: 12px 24px
    height: 52px
  field-label:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
  required-mark:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.error}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  text-input-hover:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  text-input-focused:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  text-input-error:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  text-input-disabled:
    backgroundColor: "{colors.field-disabled}"
    textColor: "{colors.ink-disabled}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  text-input-readonly:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 48px
  select:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 40px 11px 16px
    height: 48px
  textarea:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.input}"
    rounded: "{rounded.md}"
    padding: 11px 16px
    height: 112px
  helper-text:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-meta}"
    typography: "{typography.helper}"
    rounded: "{rounded.none}"
  error-text:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.error}"
    typography: "{typography.helper}"
    rounded: "{rounded.none}"
  file-dropzone:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 24px
    height: 128px
  file-dropzone-active:
    backgroundColor: "{colors.band-blue}"
    textColor: "{colors.primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 24px
    height: 128px
  file-item:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: 8px 12px
    height: 48px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  button-primary-pressed:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary-hover}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  button-ghost:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 16px
    height: 48px
  button-danger:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  button-danger-outline:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.error}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 4px 12px
    height: 36px
  button-add-row:
    backgroundColor: "{colors.add-row}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  pos-row-num:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    height: 24px
  button-disabled:
    backgroundColor: "{colors.field-disabled}"
    textColor: "{colors.ink-disabled}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 48px
  tag-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  tag-warning:
    backgroundColor: "{colors.warning-bg}"
    textColor: "{colors.warning}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  tag-error:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  tag-info:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.primary-hover}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  tag-neutral:
    backgroundColor: "{colors.band}"
    textColor: "{colors.ink-body}"
    typography: "{typography.badge}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  inline-notification:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: 12px 16px
  data-table-header:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    typography: "{typography.table-header}"
    rounded: "{rounded.none}"
    padding: 12px 16px
    height: 48px
  data-table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.table-cell}"
    rounded: "{rounded.none}"
    padding: 12px 16px
    height: 48px
  data-table-row-hover:
    backgroundColor: "{colors.band-blue}"
    textColor: "{colors.ink-body}"
    typography: "{typography.table-cell}"
    rounded: "{rounded.none}"
    padding: 12px 16px
    height: 48px
  modal:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 32px
  toast:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 12px 16px
  footer:
    backgroundColor: "{colors.band}"
    textColor: "{colors.ink-nav}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: 24px
---

## Overview

ระบบนี้ออกแบบสำหรับ **แอปพลิเคชันกรอกข้อมูลของหน่วยงานราชการไทย** เช่น ระบบบันทึกข้อมูลบุคคลและการประเมินผลงาน หน้าเว็บประกอบด้วยฟอร์มยาวหลายส่วน ตารางรายการ และหน้าสรุป ผู้ใช้คือเจ้าหน้าที่ที่ใช้งานทุกวัน มีทุกช่วงอายุ ใช้ทั้งเมาส์และคีย์บอร์ด

ที่มาของแต่ละส่วน:

- **จาก SAP (หน้าตา):** ใช้พื้นขาวเป็นพื้นที่ทำงาน วางบนหน้าเทาอ่อน `{colors.page}` ใช้น้ำเงิน `{colors.primary}` สีเดียวกับทุกสิ่งที่กดได้ ปุ่มและช่องต่าง ๆ มุม 8px ตัวอักษรไล่โทนเทาอมน้ำเงิน (slate) และไม่ใช้ letter-spacing
- **จาก IBM Carbon (กลไกฟอร์ม):** กลไกสถานะของช่องกรอก (focus, error, disabled) มีสีสถานะครบ (สำเร็จ / เตือน / ผิดพลาด / ข้อมูล) ใช้กริด 4px และปุ่มหรือช่องที่กดได้สูงอย่างน้อย 48px
- **ปรับเพิ่มสำหรับไทยและราชการ:** ใช้ฟอนต์ Noto Sans Thai, ระยะบรรทัดเผื่อสระบนสระล่าง, ตัวอักษรเนื้อหาขั้นต่ำ 14px และใช้แถบหัวสีน้ำเงินเข้ม `{colors.header}` เพื่อให้ยังดูเป็นเว็บของหน่วยงานรัฐ

**ลักษณะสำคัญ:**
- โครงหน้ามีสามชั้น คือ แถบหัวน้ำเงินเข้ม → แถบแท็บสีขาว → พื้นที่ทำงานสีเทาอ่อนที่มีการ์ดฟอร์มสีขาววางเรียงกัน
- น้ำเงินเป็น **สีที่ใช้ทำงาน** สงวนไว้สำหรับปุ่ม ลิงก์ แท็บที่เลือก และกรอบ focus
- แดงใช้กับ **ข้อผิดพลาดและการกระทำที่ลบหรือย้อนไม่ได้เท่านั้น** ห้ามใช้เป็นสีปุ่มทั่วไป
- แบ่งลำดับชั้นด้วยการเปลี่ยนสีพื้นและเส้นบาง 1px ไม่ใช้เงา
- ทุกข้อความภาษาไทยมีช่องไฟตัวอักษร 0 และระยะบรรทัดอย่างน้อย 1.4

## Colors

### สีหลัก
- **Primary** (`{colors.primary}` #0057d2): ปุ่มหลัก ลิงก์ แท็บที่เลือก กรอบ focus และป้ายตัวเลข
- **Primary Hover** (`{colors.primary-hover}` #0040b0): สถานะ hover ของปุ่มหลัก และสีตัวอักษรของปุ่มรอง
- **Primary Pressed** (`{colors.primary-pressed}` #022879): สถานะกดค้างของปุ่มหลัก
- **Header** (`{colors.header}` #0040b0): แถบหัวของระบบ ใช้สีทึบเรียบ ไม่ไล่สี

### พื้นผิว
- **Page** (`{colors.page}` #f5f6f7): พื้นหลังของหน้าทั้งหมด หัวตาราง
- **Canvas** (`{colors.canvas}` #ffffff): การ์ดฟอร์ม แถบแท็บ ตาราง และ modal
- **Field** (`{colors.field}` #f5f6f7): พื้นของรายการไฟล์ที่อัปโหลด (ช่องกรอกใช้พื้น `{colors.canvas}` ดูข้อยกเว้นของระบบนี้)
- **Band Blue** (`{colors.band-blue}` #ebf8ff): หัวข้อแต่ละส่วนแบบปกติ แถวตารางเมื่อ hover และพื้นของช่องอัปโหลดเมื่อลากไฟล์มาวาง
- **Band** (`{colors.band}` #eaecee): footer และช่องที่ปิดใช้งาน

### เส้น
- **Hairline** (`{colors.hairline}` #d5dadd): ขอบการ์ด เส้นแบ่งแถวตาราง และเส้นใต้แถบแท็บ เป็นเส้นตกแต่ง ไม่ได้ใช้ระบุขอบเขตของส่วนที่ต้องโต้ตอบ
- **Field Border** (`{colors.field-border}` #d0d8e3): กรอบช่องกรอก ตามหน้าตาเดิมของระบบ (ข้อยกเว้นของระบบนี้)
- **Border Strong** (`{colors.border-strong}` #8d8d8d): ขอบช่องอัปโหลด ความต่างของสีกับพื้นอย่างน้อย 3:1 ตาม WCAG 1.4.11
- **Focus** (`{colors.focus}` #0057d2): กรอบ 2px รอบส่วนที่กำลัง focus

### ตัวอักษร
| Token | สี | ใช้กับ |
|---|---|---|
| `{colors.ink}` | #0b1d33 | หัวข้อ ข้อความที่ผู้ใช้พิมพ์ในช่องกรอก |
| `{colors.ink-heading-on-band}` | #022879 | หัวข้อส่วนที่วางบน `band-blue` |
| `{colors.ink-body}` | #223548 | เนื้อหาทั่วไป ข้อความในตาราง |
| `{colors.ink-label}` | #354a5f | (ไม่ใช้กับ label แล้ว label ใช้ `{colors.primary}` ดูข้อยกเว้นของระบบนี้) |
| `{colors.ink-meta}` | #475e75 | ข้อความช่วยเหลือ คำอธิบาย placeholder |
| `{colors.ink-nav}` | #545454 | แท็บที่ไม่ได้เลือก และ footer |
| `{colors.ink-disabled}` | #8c8c8c | ข้อความในช่องที่ปิดใช้งาน (ได้รับยกเว้นเรื่องความต่างของสี) |

### สีสถานะ
| สถานะ | สีหลัก | พื้น | ใช้กับ |
|---|---|---|---|
| สำเร็จ | `{colors.success}` #198038 | `{colors.success-bg}` | บันทึกสำเร็จ สถานะ "เชื่อมต่อแล้ว" |
| เตือน | `{colors.warning}` #8e6a00 (ตัวอักษร), `{colors.warning-fill}` #f1c21b (ไอคอน) | `{colors.warning-bg}` | ทำงานแบบออฟไลน์ ข้อมูลยังไม่ได้ส่ง |
| ผิดพลาด | `{colors.error}` #da1e28 | `{colors.error-bg}` | กรอกผิด เครื่องหมาย * ช่องบังคับ ปุ่มลบ |
| ข้อมูล | `{colors.info}` #0057d2 | `{colors.info-bg}` | ข้อความแนะนำ คำชี้แจง |
| กลาง | `{colors.ink-body}` #223548 | `{colors.band}` | เรื่องที่จบตามปกติแต่ไม่ใช่ทั้งสำเร็จและผิดพลาด เช่น ถอนคำขอ |

ห้ามใช้สีอย่างเดียวในการบอกสถานะ ต้องมีไอคอนหรือข้อความกำกับเสมอ

## Typography

### ฟอนต์
- **Noto Sans Thai** (Variable, น้ำหนัก 100–900, SIL Open Font License, มีบน Google Fonts) เป็นฟอนต์หลัก เลือกเพราะเป็น variable font ที่ใช้น้ำหนัก 350 ได้จริง ตามแนวทางของ SAP ที่แยก list-item (350) ออกจากข้อความทั่วไป (400)
- Font stack: `"Noto Sans Thai", "Noto Sans", "IBM Plex Sans Thai", Tahoma, sans-serif`
- ใส่ `"Noto Sans"` ไว้ถัดไปเพื่อให้ตัวอักษรละตินและตัวเลขมีหน้าตาเข้ากัน
- ถ้าจำเป็นต้องใช้ **TH Sarabun New** หรือ **Sarabun** ตามระเบียบงานสารบรรณ ให้ใช้กับ **เอกสาร PDF ที่สร้างออกมาเท่านั้น** ไม่ใช้บนหน้าจอ เพราะตัวเล็กเมื่อเทียบที่ขนาด px เดียวกัน

### ลำดับขนาด
| Token | ขนาด | น้ำหนัก | ระยะบรรทัด | ใช้กับ |
|---|---|---|---|---|
| `{typography.page-title}` | 28px | 600 | 1.4 | ชื่อหน้า (ถ้ามี) |
| `{typography.header-title}` | 18px | 600 | 1.4 | ชื่อระบบบนแถบหัว |
| `{typography.section-title}` | 18px | 600 | 1.5 | หัวข้อแต่ละส่วน เช่น "ส่วนที่ 1 : ข้อมูลส่วนตัว" |
| `{typography.subhead}` | 16px | 600 | 1.5 | หัวข้อย่อยภายในส่วน |
| `{typography.body}` | 16px | 400 | 1.7 | เนื้อหาทั่วไป |
| `{typography.list-item}` | 16px | 350 | 1.6 | รายการในหน้าสรุป |
| `{typography.input}` | 16px | 400 | 1.5 | ข้อความในช่องกรอก (16px กันไม่ให้ iOS ซูมเมื่อแตะช่อง) |
| `{typography.button}` | 16px | 500 | 1.5 | ปุ่มทุกแบบ |
| `{typography.tab}` / `{typography.tab-active}` | 16px | 400 / 600 | 1.5 | แท็บ |
| `{typography.table-cell}` | 15px | 400 | 1.6 | ข้อมูลในตาราง |
| `{typography.label}` | 14px | 500 | 1.5 | label ของช่องกรอก |
| `{typography.body-sm}` | 14px | 400 | 1.6 | ข้อความรอง |
| `{typography.helper}` | 14px | 400 | 1.5 | ข้อความช่วยเหลือและข้อความแจ้งข้อผิดพลาด |
| `{typography.table-header}` | 14px | 600 | 1.5 | หัวตาราง |
| `{typography.caption}` | 14px | 400 | 1.5 | คำอธิบายเล็ก ชื่อระบบภาษาอังกฤษบนแถบหัว |
| `{typography.badge}` | 13px | 600 | 1.4 | ป้ายตัวเลขและป้ายสถานะเท่านั้น |

### กฎสำหรับภาษาไทย
1. **ช่องไฟตัวอักษร 0 ทุกระดับ** ห้ามนำค่า `letter-spacing: 0.16px` ของ Carbon มาใช้ เพราะทำให้สระและวรรณยุกต์แยกจากพยัญชนะ
2. **ระยะบรรทัดขั้นต่ำ 1.4 สำหรับหัวข้อ, 1.5 สำหรับข้อความทั่วไป** ภาษาไทยมีสระบน วรรณยุกต์ และสระล่าง ซ้อนกันได้ถึงสี่ระดับ ค่า 1.1–1.3 ของ IBM และ SAP จะทำให้เครื่องหมายเหล่านี้ชนกันหรือถูกตัด
3. **ห้ามกำหนดความสูงตายตัวพร้อม `overflow: hidden` กับข้อความไทย** ให้ใช้ `min-height` แทน เพื่อไม่ให้สระบนและวรรณยุกต์ถูกตัด
4. **ข้อความทั่วไปขนาดขั้นต่ำ 14px** ใช้ 13px ได้เฉพาะป้ายที่เป็นตัวเลขหรือคำสั้นมาก
5. **น้ำหนักขั้นต่ำ 350** ห้ามใช้ 300 ลงไปกับภาษาไทย ไม่นำหัวข้อตัวบาง 300 ของ IBM มาใช้
6. **การตัดคำ** ใช้ `word-break: normal; overflow-wrap: anywhere;` ห้ามใช้ `word-break: break-all` เพราะจะตัดกลางคำไทย
7. **ไม่มีตัวพิมพ์ใหญ่ทั้งคำ** สำหรับคำภาษาอังกฤษในหัวข้อและป้าย ให้ใช้รูปแบบ sentence case ตามแนวทางของ Carbon
8. **ตัวเลข** ใช้เลขอารบิกเป็นค่าเริ่มต้น และใช้ `font-variant-numeric: tabular-nums` ในตารางและช่องตัวเลข ส่วนเลขไทยใช้เฉพาะเอกสารราชการที่สร้างเป็น PDF
9. **วันที่** แสดงเป็นปีพุทธศักราช เช่น `27 ต.ค. 2569` หรือ `27 ตุลาคม 2569` แต่เก็บในฐานข้อมูลเป็น ISO 8601 (ค.ศ.)

## Layout

### ระบบระยะห่าง
- **หน่วยพื้นฐาน 4px** (กริด 4px ของ Carbon)
- Tokens: `{spacing.xxs}` 4 · `{spacing.xs}` 8 · `{spacing.sm}` 12 · `{spacing.md}` 16 · `{spacing.lg}` 24 · `{spacing.xl}` 32 · `{spacing.xxl}` 48 · `{spacing.section}` 64
- ระยะภายในการ์ดฟอร์ม `{spacing.lg}` 24px (มือถือ 16px)
- ระยะห่างระหว่างการ์ดฟอร์ม `{spacing.lg}` 24px
- ระยะระหว่าง label กับช่องกรอก `{spacing.xxs}` 4px และระหว่างช่องกรอกกับข้อความช่วยเหลือ `{spacing.xxs}` 4px
- ระยะห่างแนวตั้งระหว่างแถวของช่องกรอก `{spacing.lg}` 24px และแนวนอนระหว่างคอลัมน์ `{spacing.md}` 16px

### กริดและความกว้าง
- พื้นที่เนื้อหากว้างสูงสุด 1440px จัดกลาง ระยะขอบซ้ายขวา 24px (มือถือ 16px)
- แถบหัวและแถบแท็บกว้างเต็มจอ
- ฟอร์มใช้กริด 12 คอลัมน์ ความกว้างของช่องกรอกตามประเภทข้อมูล:

| ประเภทช่อง | ≥1056px | 672–1055px | <672px |
|---|---|---|---|
| คำนำหน้า / ระดับ / ตัวเลขสั้น | 3 คอลัมน์ | 6 คอลัมน์ | 12 |
| ชื่อ / นามสกุล / ตำแหน่ง | 4–5 คอลัมน์ | 6 คอลัมน์ | 12 |
| หน่วยงาน / สังกัด | 4 คอลัมน์ | 12 คอลัมน์ | 12 |
| ข้อความยาว / textarea / ช่องอัปโหลด | 12 คอลัมน์ | 12 | 12 |

ห้ามยืดช่องสั้น เช่น "ตำแหน่งเลขที่" ให้กว้างเต็มแถว ความกว้างของช่องควรบอกผู้ใช้ว่าต้องกรอกข้อมูลยาวแค่ไหน

### Breakpoints (จาก Carbon)
| ชื่อ | ความกว้าง | สิ่งที่เปลี่ยน |
|---|---|---|
| Mobile | < 672px | ฟอร์ม 1 คอลัมน์, แท็บเลื่อนแนวนอน, ซ่อนชื่อระบบภาษาอังกฤษบนแถบหัว, ปุ่มกว้างเต็มแถว |
| Tablet | 672–1055px | ฟอร์ม 2 คอลัมน์ |
| Desktop | 1056–1583px | ฟอร์มตามตารางด้านบน |
| Max | ≥ 1584px | พื้นที่เนื้อหาคงที่ 1440px ส่วนที่เหลือเป็นขอบ |

### ขนาดที่กดได้
- ปุ่ม ช่องกรอก select แท็บ และแถวตาราง สูง 48px ทุกขนาดหน้าจอ
- ปุ่มไอคอนอย่างเดียว เช่น ลบไฟล์หรือปิด modal ต้องมีพื้นที่กดอย่างน้อย 44×44px

## Elevation & Depth

| ระดับ | วิธีแสดง | ใช้กับ |
|---|---|---|
| 0 | พื้น `{colors.page}` | พื้นหลังหน้า |
| 1 | พื้น `{colors.canvas}` + เส้น 1px `{colors.hairline}` | การ์ดฟอร์ม ตาราง แถบแท็บ |
| 2 | พื้น `{colors.band-blue}` | หัวข้อแต่ละส่วน แถวที่ hover |
| 3 | กรอบ focus 2px `{colors.focus}` ห่างออกไป 2px | ส่วนที่กำลัง focus |
| 4 | เงา `0 8px 24px rgba(11, 29, 51, 0.16)` | modal, toast และเมนู dropdown **เท่านั้น** |

ไม่ใช้เงากับการ์ด ปุ่ม หรือช่องกรอก (ทั้ง SAP และ IBM ตรงกันในข้อนี้) เงาสงวนไว้สำหรับสิ่งที่ลอยอยู่เหนือหน้าจริง ๆ

## Shapes

| Token | ค่า | ใช้กับ |
|---|---|---|
| `{rounded.none}` | 0 | แถบหัว แถบแท็บ แถวตาราง footer (ทุกอย่างที่กว้างเต็มจอ) |
| `{rounded.sm}` | 4px | ข้อความแจ้งเตือน |
| `{rounded.md}` | 8px | ปุ่ม การ์ดฟอร์ม หัวข้อส่วน (เฉพาะมุมบน) ช่องอัปโหลด toast |
| `{rounded.lg}` | 12px | modal |
| `{rounded.pill}` | 9999px | ป้ายตัวเลข ป้ายสถานะ ป้ายสถานะการเชื่อมต่อบนแถบหัว **เท่านั้น** ห้ามใช้กับปุ่ม |

## Components

### แถบหัว (`gov-header`)
- พื้น `{colors.header}` สีทึบ ไม่ไล่สี และไม่มีเส้นทองหรือสีที่สองใต้แถบ สูง 64px
- ซ้าย: ตราหน่วยงาน (สูง 40px) → ชื่อระบบภาษาไทย `{typography.header-title}` → ชื่อภาษาอังกฤษ `header-subtitle` ด้านล่าง
- ขวา: `header-status-chip` แสดงสถานะการเชื่อมต่อ มีจุดสีอยู่หน้าข้อความ
  - กำลังเชื่อมต่อ: จุด `{colors.ink-meta}` + "กำลังเชื่อมต่อ..."
  - ออนไลน์: จุด `{colors.success}` + "เชื่อมต่อแล้ว"
  - ออฟไลน์ในระบบที่บันทึกลงเครื่องได้ (เช่น LocalStorage): จุด `{colors.warning-fill}` + "ออฟไลน์ (บันทึกในเครื่อง)" **ไม่ใช้สีแดง** เพราะผู้ใช้ยังทำงานต่อได้
  - ออฟไลน์ในระบบที่บันทึกลงเครื่องไม่ได้: จุด `{colors.error}` + "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — บันทึกไม่ได้" ใช้สีแดงเพราะผู้ใช้ทำงานต่อไม่ได้

### แท็บ (`tab-bar`, `tab`, `tab-active`)
- แถบสีขาวเต็มความกว้าง มีเส้นใต้ 1px `{colors.hairline}`
- แท็บที่เลือก: ตัวอักษร `{colors.primary}` น้ำหนัก 600 มีเส้นใต้ 3px `{colors.primary}` (เส้นทับเส้น hairline)
- แท็บที่ไม่ได้เลือก: `{colors.ink-nav}` เมื่อ hover พื้นเป็น `{colors.page}`
- ไอคอนนำหน้าขนาด 16px ห่างจากข้อความ 8px
- `count-badge` ต่อท้ายชื่อแท็บ (เช่น จำนวนรายการ) ใช้ **สีน้ำเงิน ไม่ใช้สีแดง** สีแดงสงวนไว้สำหรับการแจ้งข้อผิดพลาด

### การ์ดฟอร์มและหัวข้อส่วน
- `form-section`: พื้นขาว ขอบ 1px `{colors.hairline}` มุม 8px ไม่มีเงา
- `section-header` (แบบปกติ): อยู่ด้านบนของการ์ด พื้น `{colors.band-blue}` ตัวอักษร `{colors.ink-heading-on-band}` มี **แถบซ้าย 4px สี `{colors.primary}`** มุมบน 8px มุมล่าง 0
- `section-header-solid` (แบบทางเลือก): พื้น `{colors.primary}` ตัวอักษรขาว ใช้เมื่อหน่วยงานต้องการคงหน้าตาแถบน้ำเงินทึบแบบเดิม **เลือกใช้แบบใดแบบหนึ่งทั้งระบบ ห้ามสลับกัน**
- ไอคอนหน้าหัวข้อ 18px รูปแบบ "ส่วนที่ 1 : ชื่อส่วน" มีช่องว่างหน้าและหลัง ":"

### ช่องกรอก (`text-input` และสถานะต่าง ๆ)
กล่องขาวขอบอ่อนตามหน้าตาเดิมของระบบ (ข้อยกเว้นของระบบนี้):
- พื้น `{colors.canvas}` **กรอบ 1px `{colors.field-border}` ครบสี่ด้าน** มุม 8px สูง 48px
- **Focus:** กรอบเป็น `{colors.focus}` และมีวงแสงจาง 4px `rgba(0, 87, 210, 0.18)` รอบช่อง วงแสงนี้คือสิ่งที่ใช้แทน outline ห้ามเอาออกโดยไม่ใส่ตัวแทน
- **Error:** กรอบ `{colors.error}` และวงแสงจางสีแดง มีไอคอนเตือนขนาด 16px ด้านขวาในช่อง และ `error-text` ใต้ช่องที่บอกวิธีแก้ เช่น "กรุณากรอกนามสกุล" ไม่ใช่แค่ "ข้อมูลไม่ถูกต้อง"
- **Disabled:** พื้น `{colors.field-disabled}` ตัวอักษร `{colors.ink-disabled}`
- **Read-only:** พื้น `{colors.page}` ใช้กับข้อมูลที่ระบบดึงมาและแก้ไขไม่ได้
- **Placeholder:** สี `{colors.ink-meta}` ใช้เป็นตัวอย่างการกรอกเท่านั้น เช่น "เช่น นักวิเคราะห์นโยบายและแผน" **ห้ามใช้ placeholder แทน label**

### Select และ textarea
- `select`: หน้าตาเหมือน `text-input` มีไอคอนลูกศรลง 16px ห่างขอบขวา 16px ตัวเลือกแรกเป็น "— เลือก —" สี `{colors.ink-meta}`
- `textarea`: สูงขั้นต่ำ 112px (ประมาณ 3 บรรทัด) ให้ผู้ใช้ปรับความสูงได้อย่างเดียว (`resize: vertical`)

### Label, ช่องบังคับ และข้อความช่วยเหลือ
- `field-label` สี `{colors.primary}` น้ำหนัก 600 ตามหน้าตาเดิมของระบบ (ข้อยกเว้นของระบบนี้) ไม่ต่อท้าย label ด้วย ":"
- `required-mark`: เครื่องหมาย `*` สี `{colors.error}` ต่อท้าย label เว้นวรรค 2px และมี `aria-hidden="true"` คู่กับ `required` บนช่องกรอก
- ใส่คำอธิบาย "ช่องที่มีเครื่องหมาย * ต้องกรอก" หนึ่งครั้งที่ด้านบนของฟอร์ม
- `helper-text` ใต้ช่องกรอก สี `{colors.ink-meta}` เชื่อมกับช่องด้วย `aria-describedby`

### ช่องอัปโหลดไฟล์ (`file-dropzone`)
- พื้นขาว ขอบประ 1px `{colors.border-strong}` มุม 8px สูงขั้นต่ำ 128px จัดกลาง
- ไอคอนอัปโหลด 24px สี `{colors.primary}` → ข้อความ "คลิกหรือลากไฟล์มาวางที่นี่" (`{typography.body-sm}`, ส่วน "คลิก" เป็นลิงก์สี `{colors.primary}`) → ข้อจำกัดประเภทและขนาดไฟล์ที่ระบบรับจริง เช่น "รองรับ PDF, Word, Excel ขนาดไม่เกิน 10 MB" สี `{colors.ink-meta}` ข้อความนี้ต้องตรงกับที่เซิร์ฟเวอร์ตรวจเสมอ
- เมื่อลากไฟล์มาวางหรือ focus: `file-dropzone-active` พื้น `{colors.band-blue}` ขอบทึบ 2px `{colors.primary}`
- หลังอัปโหลดแสดง `file-item`: ไอคอน PDF → ชื่อไฟล์ → ขนาดไฟล์ → ปุ่มลบ (ไอคอน ×, มี `aria-label="ลบไฟล์"`)
- ไฟล์ผิดประเภทหรือใหญ่เกิน: แสดง `error-text` ใต้ช่อง ขอบเปลี่ยนเป็น `{colors.error}`

### ปุ่ม
| ประเภท | ใช้เมื่อ | หน้าตา |
|---|---|---|
| `button-primary` | การกระทำหลักของหน้า เช่น บันทึก ส่ง **Download PDF** | พื้น `{colors.primary}` ตัวอักษรขาว |
| `button-secondary` | การกระทำรอง เช่น ดูตัวอย่าง PDF ยกเลิก | พื้นขาว ขอบ 1px `{colors.primary}` ตัวอักษร `{colors.primary-hover}` |
| `button-ghost` | การกระทำเล็ก ๆ ในตาราง หรือลิงก์ที่เป็นปุ่ม | ไม่มีพื้น ตัวอักษร `{colors.primary}` เมื่อ hover พื้นเป็น `{colors.page}` |
| `button-danger` | ลบรายการ ล้างฟอร์ม (สิ่งที่ย้อนกลับไม่ได้) | พื้น `{colors.error}` ตัวอักษรขาว |
| `button-disabled` | ปุ่มที่ยังกดไม่ได้ | พื้น `{colors.field-disabled}` ตัวอักษร `{colors.ink-disabled}` |

- ทุกปุ่มสูง 48px มุม 8px ไอคอน 16–20px ห่างข้อความ 8px
- ปุ่มหลักมีได้ **หนึ่งปุ่มต่อหนึ่งกลุ่มการกระทำ**
- ลำดับปุ่มในแถว: ปุ่มรองอยู่ซ้าย ปุ่มหลักอยู่ขวาสุด
- `button-danger` ต้องมี modal ยืนยันก่อนทำงาน

### ป้ายสถานะ (`tag-*`) และข้อความแจ้งเตือน (`inline-notification`)
- ป้ายสถานะเป็นทรง pill ใช้คู่สีพื้นและตัวอักษรตามตารางสีสถานะ เช่น "บันทึกแล้ว" (สำเร็จ), "รอตรวจสอบ" (เตือน), "ถูกตีกลับ" (ผิดพลาด), "ฉบับร่าง" (ข้อมูล), "ถอนคำขอ" (กลาง `tag-neutral`)
- ข้อความแจ้งเตือนในหน้า: พื้นตามสถานะ แถบซ้าย 4px สีหลักของสถานะ ไอคอน 20px หัวข้อตัวหนา และข้อความ ใช้ `role="status"` สำหรับข้อมูลทั่วไป และ `role="alert"` สำหรับข้อผิดพลาด
- เมื่อส่งฟอร์มแล้วมีข้อผิดพลาด แสดงข้อความแจ้งเตือนสรุปที่ด้านบนของฟอร์ม พร้อมลิงก์ไปยังแต่ละช่องที่ผิด แล้วย้าย focus ไปที่ข้อความสรุปนั้น

### ตาราง (`data-table-*`)
- หัวตาราง: พื้น `{colors.page}` ตัวอักษร `{typography.table-header}` สี `{colors.ink}` สูง 48px
- แถว: พื้นขาว สูง 48px เส้นแบ่งแถว 1px `{colors.hairline}` ไม่สลับสีแถว hover เป็น `{colors.band-blue}`
- ตัวเลขชิดขวาและใช้ `tabular-nums` ข้อความชิดซ้าย การกระทำในแถวใช้ `button-ghost` ชิดขวา
- หน้าจอเล็กกว่า 672px: ตารางเลื่อนแนวนอนได้ โดยคอลัมน์แรก (ชื่อ) ตรึงไว้
- ไม่มีข้อมูล: แสดงข้อความ "ยังไม่มีรายการ" จัดกลาง พร้อมปุ่ม "เพิ่มรายการ" แบบ `button-secondary`

### Modal และ toast
- `modal`: กว้างสูงสุด 560px มุม 12px มีเงาระดับ 4 พื้นหลังมืดลง `rgba(11, 29, 51, 0.5)` และ focus ต้องวนอยู่ใน modal ระหว่างเปิด
- `toast`: มุมล่างขวา มีแถบซ้าย 4px สีสถานะ หายไปเองหลัง 5 วินาที ยกเว้น toast แจ้งข้อผิดพลาดที่ต้องปิดเอง

### Footer
- พื้น `{colors.band}` ตัวอักษร `{typography.caption}` สี `{colors.ink-nav}` แสดงชื่อหน่วยงาน เวอร์ชันของระบบ และช่องทางติดต่อผู้ดูแลระบบ

## Accessibility

- ใช้ **WCAG 2.1 ระดับ AA** เป็นเกณฑ์ขั้นต่ำ
- ข้อความทั่วไปต้องมีความต่างของสีกับพื้นอย่างน้อย 4.5:1 และเส้นขอบของส่วนที่ต้องโต้ตอบอย่างน้อย 3:1 (ทุก token ของข้อความและ `{colors.border-strong}` ผ่านเกณฑ์นี้บนพื้นขาว)
- ทุกช่องกรอกมี `<label for>` ที่เชื่อมกันจริง ไม่ใช้ placeholder แทน label
- ใช้งานได้ด้วยคีย์บอร์ดอย่างเดียว ลำดับ Tab ต้องไล่ตามลำดับที่มองเห็น และเห็นกรอบ focus ทุกครั้ง
- ข้อผิดพลาดต้องบอกด้วยข้อความและไอคอน ไม่ใช่สีอย่างเดียว ช่องที่ผิดมี `aria-invalid="true"`
- ใส่ `lang="th"` ที่ `<html>` เพื่อให้โปรแกรมอ่านหน้าจออ่านภาษาไทยได้ถูกต้อง

## ข้อยกเว้นของระบบนี้

เมื่อ 27 ต.ค. 2569 ผู้ใช้ขอให้ส่วนประกอบสี่อย่างในฟอร์มกลับไปเป็นหน้าตาเดิมของระบบ ซึ่งขัดกับกฎทั่วไปในไฟล์นี้ จึงบันทึกเป็นข้อยกเว้นไว้ที่นี่ ส่วนอื่นของหน้ายังใช้กฎปกติ

| ส่วนประกอบ | หน้าตา | กฎที่ยกเว้น |
|---|---|---|
| `field-label` | สี `{colors.primary}` น้ำหนัก 600 ทุก label ในระบบ | ห้ามใช้สีน้ำเงินกับ label |
| `text-input`, `select`, `textarea` | กล่องขาว กรอบ `{colors.field-border}` มุม 8px focus เป็นขอบน้ำเงินกับวงแสงจาง | ช่องพื้นเทามีเส้นใต้ของ Carbon และเกณฑ์ 3:1 ของขอบ |
| `pos-row-num` และปุ่มลบแถวตำแหน่ง (`button-danger-outline`) | วงกลมน้ำเงินทึบเลขขาว และปุ่ม "ลบ" ขอบแดงตัวแดง ไม่มี modal เพราะแถวยังไม่ถูกบันทึก | — (ปุ่มลบใช้สีแดงตามกฎอยู่แล้ว) |
| `button-add-row` | ไล่สีเขียว `{colors.add-row}` → `{colors.add-row-end}` ตัวอักษรขาว จัดกลางใต้แถว | ห้ามไล่สี และสีที่ใช้ทำงานคือน้ำเงิน |

กรอบช่องกรอก `{colors.field-border}` ต่างจากพื้นขาวประมาณ 1.4:1 ต่ำกว่าเกณฑ์ 3:1 ของ WCAG 1.4.11 ผู้ใช้ยังเห็นช่องได้จาก label และพื้นการ์ด แต่ถ้าต้องผ่านเกณฑ์ ให้เปลี่ยน `{colors.field-border}` เป็น `{colors.border-strong}`

ตัวอักษรขาวบนปลายสีเขียวอ่อน `{colors.add-row-end}` มีความต่างของสีประมาณ 2.1:1 ต่ำกว่าเกณฑ์ 4.5:1 ของ WCAG AA ฝั่งเขียวเข้มผ่านเกณฑ์ ถ้าต้องผ่าน AA ทั้งปุ่ม ให้เปลี่ยน `{colors.add-row-end}` เป็นสีที่เข้มพอ

## Do's and Don'ts

### Do
- ใช้ `{colors.primary}` กับสิ่งที่กดได้เท่านั้น ได้แก่ ปุ่ม ลิงก์ แท็บที่เลือก และกรอบ focus
- ใช้สีแดง `{colors.error}` เฉพาะข้อผิดพลาด เครื่องหมาย * และการกระทำที่ลบหรือย้อนไม่ได้
- ตั้ง `letter-spacing: 0` และระยะบรรทัดอย่างน้อย 1.4 กับข้อความไทยทุกที่
- แบ่งลำดับชั้นด้วยการเปลี่ยนสีพื้นและเส้น 1px
- กำหนดความกว้างของช่องกรอกตามความยาวของข้อมูลที่ต้องกรอก
- เขียนข้อความแจ้งข้อผิดพลาดที่บอกวิธีแก้
- ทุกระยะห่างเป็นผลคูณของ 4px

### Don't
- ห้ามใช้แถบหัวแบบไล่สี และห้ามเพิ่มสีที่สอง เช่น เส้นทองใต้แถบหัว
- ห้ามใช้สีไล่ระดับกับส่วนอื่น ยกเว้น `button-add-row`
- ห้ามใช้ปุ่มสีแดงกับการกระทำปกติ เช่น ดาวน์โหลด หรือพิมพ์
- ห้ามใช้สีน้ำเงินกับข้อความทั่วไป (label เป็นข้อยกเว้นของระบบนี้)
- ห้ามใส่เงาให้การ์ด ปุ่ม หรือช่องกรอก
- ห้ามใช้ปุ่มทรง pill และห้ามใช้มุมเกิน 12px
- ห้ามใช้ฟอนต์น้ำหนักต่ำกว่า 350 หรือขนาดต่ำกว่า 14px กับข้อความไทยทั่วไป
- ห้ามใช้ `word-break: break-all` กับข้อความไทย
- ห้ามลบ outline ตอน focus โดยไม่มีสิ่งแทน
- ห้ามสลับใช้ `section-header` และ `section-header-solid` ในระบบเดียวกัน

## Iteration Guide

1. แก้ทีละส่วนประกอบ และอ้างถึงด้วยชื่อ token ใน `components:` เช่น `text-input-error`
2. ส่วนประกอบใหม่ที่ไม่มีในไฟล์นี้ ให้ดูแนวทางใน Carbon Design System ก่อน แล้วปรับมุม (8px) สี และตัวอักษรตามไฟล์นี้
3. เพิ่มสถานะใหม่เป็น component แยก เช่น `button-primary-hover` ไม่แก้ทับของเดิม
4. หลังแก้ไฟล์ ตรวจด้วย `npx @google/design.md lint DESIGN.md`
5. ทดสอบหน้าจอใหม่ด้วยข้อความไทยที่มีสระบน วรรณยุกต์ และสระล่างซ้อนกัน เช่น "ผู้ปฏิบัติงานที่ได้รับเลือก" เพื่อเช็กว่าไม่มีเครื่องหมายถูกตัด

## Known Gaps

- **โหมดมืด** ยังไม่ได้กำหนด ต้นฉบับทั้ง SAP และ IBM ไม่มีชุดสีมืดให้
- **ตัวเลือกวันที่ (date picker)** และ **combobox ที่ค้นหาได้** (เช่น เลือกหน่วยงานจากรายการยาว) ยังไม่ได้กำหนด ให้ใช้แนวทางของ Carbon แล้วปรับตามไฟล์นี้ โดยปฏิทินต้องแสดงปีเป็น พ.ศ.
- **รูปแบบเอกสาร PDF ที่ระบบสร้าง** อยู่นอกขอบเขตของไฟล์นี้ ให้ทำตามระเบียบงานสารบรรณ
- ค่าสีตั้งต้นมาจากการวิเคราะห์เว็บไซต์ SAP และ IBM บน getdesign.md ซึ่งเป็นการวิเคราะห์อิสระ ไม่เกี่ยวข้องกับ SAP หรือ IBM ควรตรวจกับคู่มืออัตลักษณ์ของหน่วยงาน (ถ้ามี) ก่อนใช้งานจริง
