import {
  Armchair, Briefcase, Building2, Church, ClipboardList, Cpu, DoorOpen,
  FlaskConical, Globe, GraduationCap, HandHeart, HeartHandshake, Hospital,
  Landmark, Laptop, Music, Presentation, Pyramid, Shield, Stethoscope,
  Toilet, Users, Utensils, Volleyball, Wallet,
} from 'lucide-react';

const LOCATION_ICONS = {
  main_entrance: DoorOpen,
  guidance_office: HeartHandshake,
  restroom_left: Toilet,
  restroom_lower: Toilet,
  san_nicolas_bldg: Building2,
  cfo: Pyramid,
  clinic: Stethoscope,
  cafeteria: Utensils,
  visitors_lodge: Armchair,
  open_court: Volleyball,
  cathedral: Church,
  sp_building: Building2,
  college_education: GraduationCap,
  cbma: Briefcase,
  chs: Hospital,
  hr_office: Users,
  dean_graduate: GraduationCap,
  presidents_office: Landmark,
  presidents_boardroom: Presentation,
  inspire: Globe,
  community_dev: HandHeart,
  ccje: Shield,
  ceit: Cpu,
  snb_building: Building2,
  registrar_office: ClipboardList,
  science_building: FlaskConical,
  sao: Users,
  student_lounge_upper: Armchair,
  student_lounge_lower: Armchair,
  finance_office: Wallet,
  ict_office: Laptop,
  maclab: Laptop,
  music_room: Music,
};

function customLocationIcon(node) {
  const name = node.name.toLowerCase();
  if (/restroom|toilet|bathroom/.test(name)) return Toilet;
  if (/entrance|\bgate\b/.test(name)) return DoorOpen;
  if (/cathedral|chapel|church/.test(name)) return Church;
  if (/court|gym/.test(name)) return Volleyball;
  if (/clinic|health|medical|nurs/.test(name)) return Stethoscope;
  if (/computer|ict|maclab|mac lab/.test(name)) return Laptop;
  if (/science|laboratory|\blab\b/.test(name)) return FlaskConical;
  if (/finance|cashier|account/.test(name)) return Wallet;
  if (/registrar|admission|record/.test(name)) return ClipboardList;
  if (/guidance|counsel/.test(name)) return HeartHandshake;
  if (/music/.test(name)) return Music;
  if (/cafeteria|canteen|dining/.test(name)) return Utensils;
  if (/lounge|lodge/.test(name)) return Armchair;
  if (/human resource|student affairs/.test(name)) return Users;
  if (/college|school/.test(name) || node.type === 'college') return GraduationCap;
  return node.type === 'building' ? Building2 : Briefcase;
}

export default function CampusLocationIcon({ node, size = 18, color = 'currentColor' }) {
  const Icon = LOCATION_ICONS[node.id] || customLocationIcon(node);
  return <Icon size={size} color={color} strokeWidth={1.8} aria-hidden="true" focusable="false"
    className="campus-location-icon" style={{ flexShrink: 0, verticalAlign: 'middle' }} />;
}
