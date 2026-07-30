/** 소진공 상권업종 대분류 — backend/project/data/industry_codes.json (lcls) */
export interface IndustryCategory {
  lcls_cd: string;
  /** API·에이전트에 전달하는 공식 명칭 */
  name: string;
  /** 화면 표시용 짧은 라벨 */
  label: string;
  examples?: string;
}

export const INDUSTRY_CATEGORIES: IndustryCategory[] = [
  {
    lcls_cd: "I2",
    name: "음식점업",
    label: "음식점업",
    examples: "한식, 카페, 주점, 치킨",
  },
  {
    lcls_cd: "G2",
    name: "소매업",
    label: "소매업",
    examples: "편의점, 슈퍼, 의류, 잡화",
  },
  {
    lcls_cd: "S2",
    name: "수리 및 개인 서비스업",
    label: "수리·개인서비스",
    examples: "미용, 세탁, 헬스, 수리",
  },
  {
    lcls_cd: "P1",
    name: "교육 서비스업",
    label: "교육 서비스업",
    examples: "학원, 교습소, 예체능",
  },
  {
    lcls_cd: "R1",
    name: "예술, 스포츠 및 여가관련 서비스업",
    label: "예술·스포츠·여가",
    examples: "PC방, 노래방, 골프, 당구",
  },
  {
    lcls_cd: "I1",
    name: "숙박업",
    label: "숙박업",
    examples: "호텔, 펜션, 게스트하우스",
  },
  {
    lcls_cd: "Q1",
    name: "보건의료업",
    label: "보건·의료",
    examples: "의원, 약국, 한의원",
  },
  {
    lcls_cd: "L1",
    name: "부동산업",
    label: "부동산업",
    examples: "중개업, 임대",
  },
  {
    lcls_cd: "M1",
    name: "전문, 과학 및 기술 서비스업",
    label: "전문·과학·기술",
    examples: "법률, 회계, 디자인",
  },
  {
    lcls_cd: "N1",
    name: "사업시설 관리, 사업 지원 및 임대 서비스업",
    label: "사업시설·임대",
    examples: "청소, 경비, 사무지원",
  },
];
