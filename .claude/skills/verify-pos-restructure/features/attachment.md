# เอกสารแนบ

คำขอหนึ่งใบแนบเอกสารได้หนึ่งไฟล์ รองรับ PDF, Word และ Excel ขนาดไม่เกิน 10 MB ไฟล์ถูกอัปโหลดทันทีที่เลือก ก่อนที่คำขอจะถูกบันทึก ชื่อไฟล์ที่เก็บบนเซิร์ฟเวอร์เป็น UUID และชื่อเดิมถูกเก็บไว้แสดงผล การลบคำขอจะลบไฟล์แนบไปด้วย

## Sub-features

- `attach-pick` เลือกไฟล์แล้วหน้าเว็บอัปโหลดให้ทันทีและแสดงชื่อกับขนาดไฟล์
- `attach-reject-type` ปฏิเสธชนิดไฟล์ที่ไม่รองรับ พร้อมบอกชนิดที่รองรับ
- `attach-open` เปิดไฟล์ที่แนบไว้จากลิงก์ `เปิดไฟล์`
- `attach-remove` ลบไฟล์ออกจากคำขอที่กำลังกรอกด้วยปุ่ม `ลบไฟล์`
- `attach-save` คำขอที่บันทึกแล้วเก็บชื่อไฟล์เดิมไว้ และตารางแสดงลิงก์ `ไฟล์`
- `attach-replace` เปลี่ยนไฟล์ของคำขอเดิม แล้วไฟล์เก่าถูกลบออกจากเซิร์ฟเวอร์
- `attach-delete-cascade` ลบคำขอแล้วไฟล์แนบถูกลบตามไปด้วย

## How to get to it (user POV)

- ในแท็บ `กรอกข้อมูล` ส่วนที่ 5 กดพื้นที่ `คลิกเพื่อเลือกไฟล์ หรือลากไฟล์มาวางที่นี่` แล้วเลือกไฟล์จากหน้าต่างของระบบ
- ลากไฟล์จากเครื่องมาวางบนพื้นที่เดียวกัน
- ในแท็บ `คำขอทั้งหมด` กดลิงก์ `ไฟล์` ในคอลัมน์ไฟล์ของแถวนั้น
- ในฟอร์มที่โหลดคำขอเดิมมาแก้ กดลิงก์ `เปิดไฟล์` ข้างชื่อไฟล์

## Driving it with control_pos.py

Preconditions:

- `$POS doctor` ผ่านทั้ง 8 ข้อ
- อยู่ที่แท็บ `กรอกข้อมูล` ด้วย `$POS browser open` แล้ว `$POS browser click --text "กรอกข้อมูล"`
- โฟลเดอร์ `uploads` ของอินสแตนซ์ว่าง ตรวจจาก `$POS data reset` แบบ dry-run ซึ่งรายงาน `would_delete_upload_files`

- **แนบไฟล์ที่รองรับ** ป้อนไฟล์ตัวอย่างให้ช่องแนบไฟล์ สั่ง `$POS browser attach --select '#file_attach' --sample pdf` ผลที่ได้คือ `ok` เป็น `true` และ `method` เป็น `DOM.setFileInputFiles` และ `after.shown` มีคำว่า `sample.pdf` กับขนาดไฟล์ และ `after.zone` เป็น `sample.pdf`
- **ยืนยันว่าไฟล์ถึงเซิร์ฟเวอร์** ไฟล์ถูกอัปโหลดแล้วแม้คำขอยังไม่ถูกบันทึก ตรวจจากชื่อ UUID ที่หน้าเว็บถืออยู่ สั่ง `$POS browser read --expr "uploadedServerFile + ' | ' + uploadedOrigName"` ค่าที่ได้เป็นชื่อ UUID ลงท้าย `.pdf` คู่กับ `sample.pdf` และไฟล์ชื่อนั้นต้องมีอยู่จริงในโฟลเดอร์ `uploads` ของอินสแตนซ์ ซึ่ง `$POS data reset` แบบ dry-run รายงานไว้ใน `would_delete_upload_files`
- **ปฏิเสธชนิดที่ไม่รองรับ** ป้อนไฟล์ `.txt` สั่ง `$POS browser attach --select '#file_attach' --sample txt` คำสั่งนี้ **คาดว่าได้ `ok` เป็น `false`** เพราะหน้าเว็บไม่แสดงชื่อไฟล์ ซึ่งเป็นพฤติกรรมที่ถูกต้อง ยืนยันเหตุผลด้วย `$POS browser read --expr "document.getElementById('toast-msg').textContent"` ซึ่งเป็น `อัปโหลดไฟล์ไม่สำเร็จ: ประเภทไฟล์ไม่รองรับ รองรับเฉพาะ PDF, Word, Excel`
- **ลิงก์เปิดไฟล์ชี้ไปที่ไฟล์จริง** สั่ง `$POS browser read --expr "(document.querySelector('#file-name-display a')||{}).getAttribute('href')"` ค่าที่ได้คือ `/uploads/<UUID>.pdf` แล้วตรวจว่าเปิดได้จริงด้วย `$POS api GET uploads/<UUID>.pdf` ซึ่งตอบ `200`
- **ลบไฟล์ออกจากฟอร์ม** กดปุ่มชื่อ `ลบไฟล์` สั่ง `$POS browser click --text "ลบไฟล์"` แล้ว `$POS browser read --expr "uploadedServerFile === '' && document.getElementById('file-info').style.display === 'none'"` ค่าที่ได้คือ `true` และพื้นที่แนบไฟล์กลับเป็นข้อความชวนเลือกไฟล์
- **บันทึกคำขอพร้อมไฟล์แนบ** แนบใหม่แล้วกรอกช่องที่จำเป็นและบันทึก สั่ง `$POS browser attach --select '#file_attach' --sample pdf` แล้ว `$POS browser fill --select '#sec1-container [name="s1_type"]' --value "ทั่วไป"` แล้ว `$POS browser fill --select '#sec1-container [name="s1_level"]' --value "อาวุโส"` แล้ว `$POS browser fill --select '#sec1-container [name="s1_no"]' --value "888"` แล้ว `$POS browser fill --select '#p4_status' --value "อนุมัติ"` แล้ว `$POS browser click --text "บันทึกคำขอ"` ข้อความที่ได้คือ `บันทึกคำขอเรียบร้อยแล้ว`
- **ตารางแสดงลิงก์ไฟล์** สั่ง `$POS browser click --text "คำขอทั้งหมด"` แล้ว `$POS browser read --table '#tbl' --wait-text "888"` แถวของคำขอนั้นมีคำว่า `ไฟล์` ในคอลัมน์ไฟล์ และ `$POS api GET api/positions` คืนคำขอใบนั้นที่มี `file_orig_name` เป็น `sample.pdf` และ `file_name` เป็นชื่อ UUID
- **เปลี่ยนไฟล์ของคำขอเดิม** โหลดคำขอมาแก้แล้วแนบไฟล์ใหม่ สั่ง `$POS browser click --text "แก้ไขคำขอ" --nth 0` แล้ว `$POS browser read --wait-text "โหลดคำขอเพื่อแก้ไขแล้ว"` แล้วจดชื่อ UUID เดิมด้วย `$POS browser read --expr "uploadedServerFile"` แล้ว `$POS browser attach --select '#file_attach' --sample docx` แล้ว `$POS browser click --text "บันทึกคำขอ"` ข้อความที่ได้คือ `อัปเดตคำขอเรียบร้อยแล้ว` และ `$POS api GET uploads/<UUID เดิม>` ตอบ `404` ซึ่งพิสูจน์ว่าไฟล์เก่าถูกลบ ไม่ใช่แค่เลิกอ้างถึง
- **ลบคำขอแล้วไฟล์หายตาม** จดชื่อ UUID ปัจจุบันจาก `$POS api GET api/positions` แล้วสั่ง `$POS browser click --text "ลบคำขอ" --nth 0` แล้ว `$POS browser click --select '#confirmOk'` แล้ว `$POS browser read --wait-text "ลบคำขอเรียบร้อย"` แล้ว `$POS api GET uploads/<UUID>` ตอบ `404` และกล่องยืนยันก่อนลบต้องมีบรรทัดว่าไฟล์แนบจะถูกลบด้วย ตรวจจาก `$POS browser read --select '#confirmBody'` ก่อนกดยืนยัน
- **หลักฐาน** สั่ง `$POS browser shot --name attachment-picked --with-text` ตอนหน้าเว็บแสดงชื่อไฟล์ และ `$POS browser shot --name attachment-rejected --with-text` ตอนถูกปฏิเสธชนิดไฟล์ และ `$POS browser shot --name attachment-in-list --with-text` ตอนตารางแสดงลิงก์ไฟล์
- **คืนสภาพ** สั่ง `$POS data reset --apply` ซึ่งลบคำขอ ไฟล์แนบ และไฟล์ที่อัปโหลดค้างไว้โดยไม่มีคำขออ้างถึง แล้ว `$POS data seed` ไฟล์ตัวอย่างใน `scaffolding` ถูกลบตอน `$POS app stop`

## Gotchas

- `#file_attach` เป็น `display:none` ซึ่งเป็นวิธีมาตรฐานของหน้าเว็บสมัยนี้ คำสั่ง `browser attach` ปิดการกรองด้วยการมองเห็นให้เฉพาะกรณีนี้ คำสั่งอื่นจะหาองค์ประกอบนี้ไม่เจอ ซึ่งถูกต้องแล้ว
- **ห้ามคลิก `#upload-zone`** พื้นที่ที่ผู้ใช้เห็นนั้นเปิดหน้าต่างเลือกไฟล์ของระบบปฏิบัติการ ซึ่งขับไม่ได้และอาจทำให้เบราว์เซอร์ค้างรอ จนคำสั่งถัดไปทั้งหมดล้ม
- การลากไฟล์มาวาง (`handleDrop`) ขับไม่ได้ ให้รายงานว่าข้าม ไม่ใช่รายงานว่าผ่านเพราะเส้นทางเลือกไฟล์ผ่าน
- ไฟล์ถูกอัปโหลดตอนเลือก ไม่ใช่ตอนบันทึกคำขอ การเลือกไฟล์แล้วไม่บันทึกคำขอทิ้งไฟล์กำพร้าไว้ในโฟลเดอร์ `uploads` ซึ่งเป็นพฤติกรรมของแอป ไม่ใช่ข้อผิดพลาด โปรเจกต์มี `cleanup_orphans.py` ไว้จัดการกับข้อมูลจริง
- แอปตรวจชนิดไฟล์จากนามสกุลเท่านั้น ไฟล์ตัวอย่างจาก `--sample` จึงไม่ต้องเป็นเอกสารจริง และ `--sample txt` คือเครื่องมือพิสูจน์เส้นทางที่ต้องถูกปฏิเสธ
- ขนาดไฟล์ถูกตรวจสองชั้น หน้าเว็บเตือนที่เกิน 10 MB ก่อนส่ง และ `MAX_CONTENT_LENGTH` ของเซิร์ฟเวอร์ตอบ 413 การพิสูจน์ชั้นเซิร์ฟเวอร์ต้องยิง `$POS api POST api/upload` ไม่ใช่ผ่านหน้าเว็บ และต้องสร้างไฟล์ใหญ่เองซึ่งไม่คุ้มกับเวลาที่ใช้ ให้ข้ามและรายงานว่าข้าม
- ชื่อไฟล์บนเซิร์ฟเวอร์เป็น UUID ที่สุ่มใหม่ทุกครั้ง **ห้ามเขียนชื่อไฟล์ตายตัวในสูตร** ให้อ่านค่าจาก `uploadedServerFile` หรือจาก `file_name` ที่ API คืนมา
- ชื่อไฟล์ UUID ปรากฏอยู่ในคำตอบของ `GET /api/positions` การเดาชื่อยากจึงไม่ใช่การป้องกัน เส้นทาง `/uploads/` อยู่ใต้ด่าน `require_login` เหมือนเส้นทางอื่น การเรียกจากเครื่องในวงที่ยังไม่เข้าสู่ระบบจะถูกพาไปหน้าเข้าสู่ระบบ ไม่ใช่ได้ไฟล์
